"""What the admin panel can see and do.

Reading one person's data and deleting an account are both written to the
audit log, in the same transaction as the read or the delete.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import storage
from backend.core.exceptions import AppError, NotFoundError, ValidationFailedError
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.modules.admin import repository
from backend.modules.admin.dependencies import Admin
from backend.modules.admin.models import AdminAction
from backend.modules.admin.schemas import (
    AdminActionRead,
    AdminApplication,
    AdminJobCheck,
    AdminResume,
    AdminStats,
    AdminUserDetail,
    AdminUserRow,
    DayCount,
    ErrorEventRead,
    ErrorGroup,
    ErrorSummary,
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
    user, profiles, resumes, job_checks, applications, integrations, extensions, last_check = row
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
    db: AsyncSession, *, search: str | None, cursor: str | None, limit: int
) -> Page[AdminUserRow]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_users(db, search=search, after=after, limit=limit + 1)
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
