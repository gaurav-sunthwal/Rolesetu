"""What the admin panel can see and do.

Reading one person's data and deleting an account are both written to the
audit log, in the same transaction as the read or the delete.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import storage
from backend.core.config import get_settings
from backend.core.email import send_email
from backend.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.db.session import get_sessionmaker
from backend.modules.admin import emails, repository
from backend.modules.admin.dependencies import Admin
from backend.modules.admin.models import AdminAction, OutreachEmail
from backend.modules.admin.schemas import (
    AdminActionRead,
    AdminApplication,
    AdminJobCheck,
    AdminResume,
    AdminStats,
    AdminUserDetail,
    AdminUserRow,
    DayCount,
    EmailDefaults,
    ErrorEventRead,
    ErrorGroup,
    ErrorSummary,
    OutreachRead,
    SiteReads,
    WaitlistRow,
)
from backend.modules.errors import repository as errors_repository
from backend.modules.matches.models import Match
from backend.modules.profiles import service as profiles_service
from backend.modules.users.models import User

logger = logging.getLogger(__name__)

DAYS_CHARTED = 14
RECENT_ROWS = 25


def _record(
    db: AsyncSession, admin: Admin, action: str, target_type: str, target_id: str, summary: str
) -> None:
    db.add(
        AdminAction(
            admin_email=admin.email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            summary=summary[:500],
        )
    )


def _to_user_row(row: repository.Fields) -> AdminUserRow:
    (
        user,
        profiles,
        resumes,
        job_checks,
        applications,
        integrations,
        extensions,
        last_check,
        last_emailed,
    ) = row
    return AdminUserRow(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        has_profile=profiles > 0,
        resumes=resumes,
        job_checks=job_checks,
        applications=applications,
        gmail_connected=integrations > 0,
        extension_connected=extensions > 0,
        last_check_at=last_check,
        last_emailed_at=last_emailed,
    )


async def stats(db: AsyncSession) -> AdminStats:
    now = datetime.now(UTC)
    since = now - timedelta(days=DAYS_CHARTED - 1)
    signups = await repository.per_day(db, User, since)
    checks = await repository.per_day(db, Match, since)
    days = [(since + timedelta(days=offset)).date() for offset in range(DAYS_CHARTED)]
    sites = await repository.preview_sites(db, now - timedelta(days=1))
    return AdminStats(
        **await repository.totals(db, now - timedelta(days=1), now - timedelta(days=7)),
        daily=[
            DayCount(day=day, signups=signups.get(day, 0), job_checks=checks.get(day, 0))
            for day in days
        ],
        sites=[
            SiteReads(host=host, read=read, failed=failed, paid=paid)
            for host, read, failed, paid in sites
        ],
    )


async def list_users(
    db: AsyncSession,
    *,
    search: str | None,
    extension_missing: bool,
    cursor: str | None,
    limit: int,
) -> Page[AdminUserRow]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_users(
        db, search=search, extension_missing=extension_missing, after=after, limit=limit + 1
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1][0] if rows else None
    return Page(
        items=[_to_user_row(row) for row in rows],
        next_cursor=encode_cursor(last.created_at, last.id) if has_more and last else None,
    )


async def user_detail(db: AsyncSession, *, admin: Admin, user_id: uuid.UUID) -> AdminUserDetail:
    row = await repository.get_user_row(db, user_id)
    if row is None:
        raise NotFoundError("User not found")
    user = _to_user_row(row)
    profile = await profiles_service.get_profile(db, user_id=user_id) if user.has_profile else None
    checks = await repository.recent_job_checks(db, user_id, RECENT_ROWS)
    applications = await repository.recent_applications(db, user_id, RECENT_ROWS)
    _record(db, admin, "user.view", "user", str(user_id), f"Opened {user.email}")
    return AdminUserDetail(
        user=user,
        profile=profile,
        job_checks=[
            AdminJobCheck(
                id=match.id,
                role=job.role,
                company=job.company,
                url=job.url,
                status=match.status,
                score=match.score,
                created_at=match.created_at,
            )
            for match, job in checks
        ],
        applications=[AdminApplication.model_validate(item) for item in applications],
        resumes=[
            AdminResume.model_validate(item) for item in await repository.resumes(db, user_id)
        ],
        gmail_last_synced_at=await repository.gmail_last_synced(db, user_id),
        emails=[
            OutreachRead.model_validate(item)
            for item in await repository.emails_for(db, user_id, RECENT_ROWS)
        ],
    )


async def delete_user(
    db: AsyncSession, *, admin: Admin, user_id: uuid.UUID, confirm_email: str
) -> None:
    """Removes the account's data: the stored resume files, then the user row,
    which takes every other row with it.

    The Firebase sign-in itself is not removed (the API holds no credentials
    for that), so the same Google account could sign up again from nothing.
    """
    user = await repository.get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if confirm_email.strip().lower() != user.email.lower():
        raise ValidationFailedError("Type the account's email address exactly to confirm.")
    for resume in await repository.resumes(db, user_id):
        try:
            await storage.delete_file(resume.storage_key)
        except AppError:
            # Deleting the account must not be blocked by one unreachable file.
            logger.exception("admin delete: could not remove a resume file user=%s", user_id)
    await db.delete(user)
    _record(db, admin, "user.delete", "user", str(user_id), f"Deleted {user.email}")


async def list_waitlist(
    db: AsyncSession, *, admin: Admin, cursor: str | None, limit: int
) -> Page[WaitlistRow]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_waitlist(db, after=after, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    if cursor is None:
        _record(db, admin, "waitlist.view", "waitlist", "extension", "Opened the waiting list")
    return Page(
        items=[WaitlistRow.model_validate(row) for row in rows],
        next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None,
    )


async def list_actions(
    db: AsyncSession, *, cursor: str | None, limit: int
) -> Page[AdminActionRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_actions(db, after=after, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[AdminActionRead.model_validate(row) for row in rows],
        next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None,
    )


async def list_errors(db: AsyncSession, *, hours: int, source: str | None) -> ErrorSummary:
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = await errors_repository.groups(db, since=since, source=source)
    # Two events of one problem in the same instant would otherwise list it twice.
    seen: set[str] = set()
    groups: list[ErrorGroup] = []
    for event, events, first_at, last_at in rows:
        if event.fingerprint in seen:
            continue
        seen.add(event.fingerprint)
        groups.append(
            ErrorGroup(
                fingerprint=event.fingerprint,
                source=event.source,
                level=event.level,
                route=event.route,
                method=event.method,
                status=event.status,
                code=event.code,
                message=event.message,
                events=events,
                first_at=first_at,
                last_at=last_at,
            )
        )
    return ErrorSummary(
        groups=groups,
        by_source=await errors_repository.counts_by_source(db, since),
    )


async def error_events(db: AsyncSession, *, fingerprint: str) -> list[ErrorEventRead]:
    events = await errors_repository.events_for(db, fingerprint, RECENT_ROWS * 2)
    if not events:
        raise NotFoundError("No such error. It may have been cleared.")
    return [ErrorEventRead.model_validate(event) for event in events]


async def clear_errors(db: AsyncSession, *, admin: Admin, fingerprint: str) -> None:
    removed = await errors_repository.delete_group(db, fingerprint)
    if removed:
        _record(db, admin, "errors.clear", "error", fingerprint, f"Cleared {removed} events")


# --- Emailing users ---------------------------------------------------------

NUDGE = "extension_nudge"
# Most people one bulk send writes to. Resend's free plan allows 100 emails a day.
MAX_PER_SEND = 50
# Someone sent this email is left alone for this long by later bulk sends.
QUIET_FOR = timedelta(days=14)
# One person is not written to twice within this time, to stop a double click.
ONE_EMAIL_PER = timedelta(hours=24)


def _require_email_set_up() -> None:
    if not get_settings().resend_api_key:
        raise ValidationFailedError(
            "Email is not set up on the server. Add RESEND_API_KEY to send from the panel."
        )


async def email_defaults(db: AsyncSession) -> EmailDefaults:
    recipients = await repository.count_nudge_recipients(db, datetime.now(UTC) - QUIET_FOR)
    return EmailDefaults(
        subject=emails.DEFAULT_SUBJECT,
        message=emails.DEFAULT_MESSAGE,
        placeholder=emails.PLACEHOLDER,
        recipients=recipients,
        max_per_send=MAX_PER_SEND,
        configured=bool(get_settings().resend_api_key),
    )


async def _deliver(
    db: AsyncSession,
    *,
    admin_email: str,
    user_id: uuid.UUID,
    address: str,
    name: str | None,
    subject: str,
    message: str,
) -> OutreachEmail:
    """Sends one email and records how it went. Never raises for a failed send."""
    settings = get_settings()
    email = emails.extension_nudge(
        subject=subject,
        message=message,
        name=emails.first_name(name),
        site_url=settings.dashboard_url,
        store_url=settings.extension_store_url,
    )
    record = OutreachEmail(
        id=uuid.uuid4(),
        user_id=user_id,
        admin_email=admin_email,
        kind=NUDGE,
        subject=email.subject[:200],
        status="sent",
    )
    try:
        await send_email(
            to=address,
            subject=email.subject,
            html=email.html,
            text=email.text,
            # Names this one email, so a retry never delivers a second copy.
            idempotency_key=f"outreach-{record.id}",
        )
    except Exception as exc:
        logger.warning("admin email to user=%s failed: %s", user_id, type(exc).__name__)
        record.status = "failed"
        record.error = "The email service refused or did not answer. Try again later."
    db.add(record)
    return record


async def email_user(
    db: AsyncSession, *, admin: Admin, user_id: uuid.UUID, subject: str, message: str
) -> OutreachRead:
    _require_email_set_up()
    user = await repository.get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if await repository.sent_lately(db, user_id, datetime.now(UTC) - ONE_EMAIL_PER):
        raise ConflictError(
            "This person was emailed in the last 24 hours. Wait before writing again."
        )
    name = await repository.full_name(db, user_id) or user.name
    record = await _deliver(
        db,
        admin_email=admin.email,
        user_id=user_id,
        address=user.email,
        name=name,
        subject=subject,
        message=message,
    )
    _record(
        db, admin, "email.send", "user", str(user_id), f"Emailed {user.email} ({record.status})"
    )
    await db.flush()
    return OutreachRead.model_validate(record)


async def start_extension_nudges(
    db: AsyncSession, *, admin: Admin, subject: str, message: str
) -> int:
    """How many people the send will reach. The sending itself runs after the
    response (see send_extension_nudges), since it takes a while.
    """
    _require_email_set_up()
    count = await repository.count_nudge_recipients(db, datetime.now(UTC) - QUIET_FOR)
    queued = min(count, MAX_PER_SEND)
    if queued:
        _record(
            db,
            admin,
            "email.bulk",
            "users",
            "extension_missing",
            f"Emailing {queued} people without the extension",
        )
    return queued


async def send_extension_nudges(admin_email: str, subject: str, message: str) -> None:
    """Writes to everyone without the extension who was not written to lately,
    one at a time, recording each. Runs in the background in its own session.
    """
    async with get_sessionmaker()() as db:
        recipients = await repository.nudge_recipients(
            db, datetime.now(UTC) - QUIET_FOR, MAX_PER_SEND
        )
        for user, full_name in recipients:
            await _deliver(
                db,
                admin_email=admin_email,
                user_id=user.id,
                address=user.email,
                name=full_name or user.name,
                subject=subject,
                message=message,
            )
            # Committed one by one, so a crash part way keeps the record of who was written to.
            await db.commit()
