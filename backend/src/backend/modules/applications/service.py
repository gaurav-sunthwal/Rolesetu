import uuid
from datetime import UTC, datetime, timedelta
from typing import get_args

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import NotFoundError
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.modules.applications import repository
from backend.modules.applications.models import Application, ApplicationEvent
from backend.modules.applications.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationRead,
    ApplicationStats,
    ApplicationStatus,
    ApplicationUpdate,
)
from backend.modules.inbox import repository as inbox_repository
from backend.modules.inbox.service import gmail_link
from backend.modules.matches import repository as matches_repository

FOLLOW_UP_AFTER = timedelta(days=7)
_SENT = ("applied", "replied", "interview", "offer", "rejected")
_RESPONDED = ("replied", "interview", "offer", "rejected")


def needs_follow_up(application: Application, now: datetime) -> bool:
    return (
        application.status == "applied"
        and application.applied_at is not None
        and application.applied_at <= now - FOLLOW_UP_AFTER
    )


def to_read(application: Application, now: datetime) -> ApplicationRead:
    read = ApplicationRead.model_validate(application)
    read.needs_follow_up = needs_follow_up(application, now)
    return read


def to_detail(application: Application, now: datetime) -> ApplicationDetail:
    detail = ApplicationDetail.model_validate(application)
    detail.needs_follow_up = needs_follow_up(application, now)
    return detail


async def _load_detail(
    db: AsyncSession, user_id: uuid.UUID, application_id: uuid.UUID
) -> ApplicationDetail:
    application = await repository.get(db, user_id, application_id, with_events=True)
    if application is None:
        raise NotFoundError("Application not found")
    return to_detail(application, datetime.now(UTC))


async def list_applications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str | None,
    search: str | None,
    cursor: str | None,
    limit: int,
) -> Page[ApplicationRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_page(
        db, user_id, status=status, search=search, after=after, limit=limit + 1
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    now = datetime.now(UTC)
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    items = [to_read(row, now) for row in rows]

    # One extra query for the whole page, not one per row.
    mails = await inbox_repository.latest_mail_per_application(
        db, user_id, [row.id for row in rows]
    )
    if mails:
        integration = await inbox_repository.get_integration(db, user_id)
        account = integration.account_email if integration else None
        for item in items:
            item.gmail_url = gmail_link(account, mails.get(item.id))
    return Page(items=items, next_cursor=next_cursor)


async def get_application(
    db: AsyncSession, *, user_id: uuid.UUID, application_id: uuid.UUID
) -> ApplicationDetail:
    return await _load_detail(db, user_id, application_id)


async def create_application(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: ApplicationCreate,
    idempotency_key: str | None,
) -> ApplicationDetail:
    if idempotency_key:
        existing = await repository.get_by_idempotency_key(db, user_id, idempotency_key)
        if existing is not None:
            return await _load_detail(db, user_id, existing.id)

    job_id: uuid.UUID | None = None
    match_score: int | None = None
    if payload.match_id is not None:
        match = await matches_repository.get(db, user_id, payload.match_id)
        if match is None:
            raise NotFoundError("Match not found")
        job_id, match_score = match.job_id, match.score

    applied_at = payload.applied_at
    if payload.status != "saved" and applied_at is None:
        applied_at = datetime.now(UTC)

    application = Application(
        user_id=user_id,
        job_id=job_id,
        match_score=match_score,
        idempotency_key=idempotency_key,
        role=payload.role,
        company=payload.company,
        url=payload.url,
        location=payload.location,
        status=payload.status,
        applied_at=applied_at,
        contact_email=payload.contact_email,
        notes=payload.notes,
    )
    application.events = [ApplicationEvent(type=payload.status, source=payload.source or "manual")]

    try:
        # A savepoint, so a lost race on the idempotency key doesn't poison the request.
        async with db.begin_nested():
            db.add(application)
    except IntegrityError:
        if not idempotency_key:
            raise
        existing = await repository.get_by_idempotency_key(db, user_id, idempotency_key)
        if existing is None:
            raise
        return await _load_detail(db, user_id, existing.id)

    return await _load_detail(db, user_id, application.id)


async def update_application(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
) -> ApplicationDetail:
    application = await repository.get(db, user_id, application_id)
    if application is None:
        raise NotFoundError("Application not found")

    changes = payload.model_dump(exclude_unset=True, exclude={"source"})
    new_status = changes.get("status")
    # role, company and status are required columns: an explicit null is ignored.
    for field in ("role", "company", "status"):
        if field in changes and changes[field] is None:
            del changes[field]

    status_changed = new_status is not None and new_status != application.status
    for field, value in changes.items():
        setattr(application, field, value)

    if status_changed:
        db.add(
            ApplicationEvent(
                application_id=application.id, type=new_status, source=payload.source or "manual"
            )
        )
        if new_status != "saved" and application.applied_at is None:
            application.applied_at = datetime.now(UTC)

    await db.flush()
    db.expire(application)
    return await _load_detail(db, user_id, application_id)


async def delete_application(
    db: AsyncSession, *, user_id: uuid.UUID, application_id: uuid.UUID
) -> None:
    application = await repository.get(db, user_id, application_id, with_events=True)
    if application is None:
        raise NotFoundError("Application not found")
    await db.delete(application)


async def get_stats(db: AsyncSession, *, user_id: uuid.UUID) -> ApplicationStats:
    counts = await repository.count_by_status(db, user_id)
    by_status: dict[str, int] = {
        status: counts.get(status, 0) for status in get_args(ApplicationStatus)
    }
    sent = sum(by_status[status] for status in _SENT)
    responded = sum(by_status[status] for status in _RESPONDED)
    follow_ups_due = await repository.count_follow_ups_due(
        db, user_id, datetime.now(UTC) - FOLLOW_UP_AFTER
    )
    return ApplicationStats(
        total=sum(by_status.values()),
        sent=sent,
        responded=responded,
        reply_rate=(responded / sent) if sent else None,
        interviews=by_status["interview"] + by_status["offer"],
        offers=by_status["offer"],
        rejections=by_status["rejected"],
        follow_ups_due=follow_ups_due,
        by_status=by_status,  # type: ignore[arg-type]
    )
