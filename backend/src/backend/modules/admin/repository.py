"""Reads across every user's rows, for the admin panel only.

Everywhere else a query is filtered by the caller's own user id. These are the
exception, which is why they live in one file and are reachable only through
routes that require an admin.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Date, Select, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.admin.models import AdminAction
from backend.modules.applications.models import Application
from backend.modules.inbox.models import Integration
from backend.modules.matches.models import Job, Match
from backend.modules.previews.models import JobPreview
from backend.modules.profiles.models import Profile
from backend.modules.resumes.models import ResumeFile
from backend.modules.users.models import User
from backend.modules.waitlist.models import WaitlistEntry

Cursor = tuple[datetime, uuid.UUID] | None
# A result row with columns of mixed kinds, unpacked by position where it is used.
Fields = tuple[Any, ...]


async def _count(db: AsyncSession, query: Select[Any]) -> int:
    return (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()


async def totals(db: AsyncSession, since: datetime) -> dict[str, int]:
    rendered_by_users = select(Job.id).where(
        Job.created_at > since, Job.job_json["listing"]["reader"].astext == "rendered"
    )
    rendered_by_visitors = select(JobPreview.id).where(
        JobPreview.created_at > since, JobPreview.reader == "rendered"
    )
    return {
        "users": await _count(db, select(User.id)),
        "users_with_profile": await _count(db, select(Profile.id)),
        "job_checks": await _count(db, select(Match.id)),
        "applications": await _count(db, select(Application.id)),
        "gmail_connected": await _count(db, select(Integration.id)),
        "waitlist": await _count(db, select(WaitlistEntry.id)),
        "previews_today": await _count(
            db, select(JobPreview.id).where(JobPreview.created_at > since)
        ),
        "paid_reads_today": await _count(db, rendered_by_users)
        + await _count(db, rendered_by_visitors),
    }


async def per_day(
    db: AsyncSession, model: type[User] | type[Match], since: datetime
) -> dict[Any, int]:
    day = cast(model.created_at, Date)
    result = await db.execute(
        select(day, func.count()).where(model.created_at > since).group_by(day)
    )
    return {row[0]: row[1] for row in result}


async def preview_sites(db: AsyncSession, since: datetime) -> list[Fields]:
    result = await db.execute(
        select(
            JobPreview.host,
            func.count().filter(JobPreview.page.is_not(None)),
            func.count().filter(JobPreview.page.is_(None)),
            func.count().filter(JobPreview.reader == "rendered"),
        )
        .where(JobPreview.created_at > since, JobPreview.host.is_not(None))
        .group_by(JobPreview.host)
        .order_by(func.count().desc())
        .limit(20)
    )
    return [tuple(row) for row in result]


def _user_rows() -> Select[Any]:
    """One row per user with the counts shown in the users table."""

    def count_of(model: Any) -> Any:
        return (
            select(func.count()).where(model.user_id == User.id).correlate(User).scalar_subquery()
        )

    last_check = (
        select(func.max(Match.created_at))
        .where(Match.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    return select(
        User,
        count_of(Profile),
        count_of(ResumeFile),
        count_of(Match),
        count_of(Application),
        count_of(Integration),
        last_check,
    )


async def list_users(
    db: AsyncSession, *, search: str | None, after: Cursor, limit: int
) -> list[Fields]:
    query = _user_rows()
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(func.lower(User.email).like(pattern), func.lower(User.name).like(pattern))
        )
    if after:
        created_at, row_id = after
        query = query.where(
            or_(User.created_at < created_at, and_(User.created_at == created_at, User.id < row_id))
        )
    result = await db.execute(query.order_by(User.created_at.desc(), User.id.desc()).limit(limit))
    return [tuple(row) for row in result]


async def get_user_row(db: AsyncSession, user_id: uuid.UUID) -> Fields | None:
    row = (await db.execute(_user_rows().where(User.id == user_id))).one_or_none()
    return tuple(row) if row is not None else None


async def recent_job_checks(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[Fields]:
    result = await db.execute(
        select(Match, Job)
        .join(Job, Job.id == Match.job_id)
        .where(Match.user_id == user_id)
        .order_by(Match.created_at.desc())
        .limit(limit)
    )
    return [tuple(row) for row in result]


async def recent_applications(
    db: AsyncSession, user_id: uuid.UUID, limit: int
) -> list[Application]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def resumes(db: AsyncSession, user_id: uuid.UUID) -> list[ResumeFile]:
    result = await db.execute(
        select(ResumeFile)
        .where(ResumeFile.user_id == user_id)
        .order_by(ResumeFile.created_at.desc())
    )
    return list(result.scalars())


async def gmail_last_synced(db: AsyncSession, user_id: uuid.UUID) -> datetime | None:
    result = await db.execute(
        select(func.max(Integration.last_synced_at)).where(Integration.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def list_waitlist(db: AsyncSession, *, after: Cursor, limit: int) -> list[WaitlistEntry]:
    query = select(WaitlistEntry)
    if after:
        created_at, row_id = after
        query = query.where(
            or_(
                WaitlistEntry.created_at < created_at,
                and_(WaitlistEntry.created_at == created_at, WaitlistEntry.id < row_id),
            )
        )
    result = await db.execute(
        query.order_by(WaitlistEntry.created_at.desc(), WaitlistEntry.id.desc()).limit(limit)
    )
    return list(result.scalars())


async def list_actions(db: AsyncSession, *, after: Cursor, limit: int) -> list[AdminAction]:
    query = select(AdminAction)
    if after:
        created_at, row_id = after
        query = query.where(
            or_(
                AdminAction.created_at < created_at,
                and_(AdminAction.created_at == created_at, AdminAction.id < row_id),
            )
        )
    result = await db.execute(
        query.order_by(AdminAction.created_at.desc(), AdminAction.id.desc()).limit(limit)
    )
    return list(result.scalars())
