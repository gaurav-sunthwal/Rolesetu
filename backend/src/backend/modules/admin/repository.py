"""Reads across every user's rows, for the admin panel only.

Everywhere else a query is filtered by the caller's own user id. These are the
exception, which is why they live in one file and are reachable only through
routes that require an admin.
"""

import uuid
from datetime import date, datetime
from typing import Any, Literal, cast

from sqlalchemy import Date, Select, and_, exists, func, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.admin.models import OutreachEmail
from backend.modules.applications.models import Application
from backend.modules.errors.models import ErrorEvent
from backend.modules.extension.models import ExtensionToken
from backend.modules.inbox.models import Integration
from backend.modules.matches.models import Job, Match
from backend.modules.previews.models import JobPreview
from backend.modules.profiles.models import Profile
from backend.modules.resumes.models import ResumeFile
from backend.modules.users.models import User
from backend.modules.waitlist.models import WaitlistEntry

Cursor = tuple[datetime, uuid.UUID] | None


def cast_select(query: Any) -> Select[Any]:
    """A typed query, for helpers that only care that it is a query."""
    return cast("Select[Any]", query)


# A result row with columns of mixed kinds, unpacked by position where it is used.
Fields = tuple[Any, ...]


async def _count(db: AsyncSession, query: Select[Any]) -> int:
    return (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()


async def dashboard(
    db: AsyncSession, *, since: datetime, active_since: datetime, chart_since: datetime
) -> dict[str, Any]:
    """Everything on the dashboard in one query: the counts, the sign-ups and
    job checks per day, and the sites table. The database is far from the API,
    so each separate query costs a full round trip.
    """

    def count(query: Select[Any]) -> Any:
        return select(func.count()).select_from(query.subquery()).scalar_subquery()

    counts = {
        "users": count(select(User.id)),
        "users_with_profile": count(select(Profile.id)),
        "job_checks": count(select(Match.id)),
        "applications": count(select(Application.id)),
        "gmail_connected": count(select(Integration.id)),
        "extension_connected": count(select(ExtensionToken.id)),
        "extension_active_week": count(
            select(ExtensionToken.id).where(ExtensionToken.last_used_at > active_since)
        ),
        "waitlist": count(select(WaitlistEntry.id)),
        "errors_today": count(select(ErrorEvent.id).where(ErrorEvent.created_at > since)),
        "previews_today": count(select(JobPreview.id).where(JobPreview.created_at > since)),
        "paid_reads_by_users": count(
            select(Job.id).where(Job.created_at > since, _read_by_paid_reader())
        ),
        "paid_reads_by_visitors": count(
            select(JobPreview.id).where(
                JobPreview.created_at > since, JobPreview.reader == "rendered"
            )
        ),
    }
    values: dict[str, Any] = {
        **counts,
        "signups_per_day": _per_day(User, chart_since),
        "checks_per_day": _per_day(Match, chart_since),
        "sites": _preview_sites(since),
    }
    row = (await db.execute(select(*(value.label(key) for key, value in values.items())))).one()
    found: dict[str, Any] = dict(row._mapping)
    found["paid_reads_today"] = found.pop("paid_reads_by_users") + found.pop(
        "paid_reads_by_visitors"
    )
    for key in ("signups_per_day", "checks_per_day"):
        found[key] = {date.fromisoformat(day): n for day, n in (found[key] or {}).items()}
    found["sites"] = [tuple(site) for site in found["sites"] or []]
    return found


def _per_day(
    model: type[User] | type[Match] | type[Application],
    since: datetime,
    until: datetime | None = None,
) -> Any:
    """{"2026-10-27": count, ...} for the rows created in the period."""
    day = sql_cast(model.created_at, Date)
    query = select(day.label("day"), func.count().label("n")).where(model.created_at > since)
    if until:
        query = query.where(model.created_at < until)
    days = query.group_by(day).subquery()
    return select(func.json_object_agg(days.c.day, days.c.n)).scalar_subquery()


async def daily(
    db: AsyncSession, *, since: datetime, until: datetime
) -> dict[str, dict[date, int]]:
    """Sign-ups, job checks and applications per day, in one query."""
    values = {
        "signups": _per_day(User, since, until),
        "job_checks": _per_day(Match, since, until),
        "applications": _per_day(Application, since, until),
    }
    row = (await db.execute(select(*(value.label(key) for key, value in values.items())))).one()
    return {
        key: {date.fromisoformat(day): n for day, n in (counts or {}).items()}
        for key, counts in row._mapping.items()
    }


def _preview_sites(since: datetime) -> Any:
    """[[host, read, failed, paid], ...] for the 20 busiest sites."""
    sites = (
        select(
            JobPreview.host.label("host"),
            func.count().filter(JobPreview.page.is_not(None)).label("read"),
            func.count().filter(JobPreview.page.is_(None)).label("failed"),
            func.count().filter(JobPreview.reader == "rendered").label("paid"),
            func.count().label("total"),
        )
        .where(JobPreview.created_at > since, JobPreview.host.is_not(None))
        .group_by(JobPreview.host)
        .order_by(func.count().desc())
        .limit(20)
        .subquery()
    )
    return select(
        func.json_agg(
            aggregate_order_by(
                func.json_build_array(sites.c.host, sites.c.read, sites.c.failed, sites.c.paid),
                sites.c.total.desc(),
            )
        )
    ).scalar_subquery()


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
    last_emailed = (
        select(func.max(OutreachEmail.created_at))
        .where(OutreachEmail.user_id == User.id, OutreachEmail.status == "sent")
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
        count_of(ExtensionToken),
        last_check,
        last_emailed,
    )


def _without_extension() -> Any:
    return ~exists(select(ExtensionToken.id).where(ExtensionToken.user_id == User.id))


UserFilter = Literal["profile", "extension", "extension_week", "gmail"]


def _has(what: UserFilter, active_since: datetime) -> Any:
    """Users who have the thing a dashboard count is about."""
    if what == "profile":
        return exists(select(Profile.id).where(Profile.user_id == User.id))
    if what == "gmail":
        return exists(select(Integration.id).where(Integration.user_id == User.id))
    token = select(ExtensionToken.id).where(ExtensionToken.user_id == User.id)
    if what == "extension_week":
        token = token.where(ExtensionToken.last_used_at > active_since)
    return exists(token)


def _after(model: Any, after: Cursor) -> Any:
    """Rows past the cursor, for lists ordered newest first."""
    assert after is not None
    created_at, row_id = after
    return or_(
        model.created_at < created_at, and_(model.created_at == created_at, model.id < row_id)
    )


async def list_users(
    db: AsyncSession,
    *,
    search: str | None,
    extension_missing: bool,
    has: UserFilter | None = None,
    active_since: datetime | None = None,
    joined: tuple[datetime, datetime] | None = None,
    after: Cursor,
    limit: int,
) -> list[Fields]:
    query = _user_rows()
    if extension_missing:
        query = query.where(_without_extension())
    if has:
        query = query.where(_has(has, active_since or datetime.min))
    if joined:
        query = query.where(User.created_at >= joined[0], User.created_at < joined[1])
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


async def all_job_checks(
    db: AsyncSession,
    *,
    since: datetime | None,
    until: datetime | None = None,
    paid: bool,
    after: Cursor,
    limit: int,
) -> list[Fields]:
    """Everyone's job checks, newest first: (match, job, user email)."""
    query = (
        select(Match, Job, User.email)
        .join(Job, Job.id == Match.job_id)
        .join(User, User.id == Match.user_id)
    )
    if since:
        query = query.where(Match.created_at >= since)
    if until:
        query = query.where(Match.created_at < until)
    if paid:
        query = query.where(_read_by_paid_reader())
    if after:
        query = query.where(_after(Match, after))
    result = await db.execute(query.order_by(Match.created_at.desc(), Match.id.desc()).limit(limit))
    return [tuple(row) for row in result]


def _read_by_paid_reader() -> Any:
    return Job.job_json["listing"]["reader"].astext == "rendered"


async def all_applications(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    after: Cursor,
    limit: int,
) -> list[Fields]:
    """Everyone's tracked applications, newest first: (application, user email)."""
    query = select(Application, User.email).join(User, User.id == Application.user_id)
    if since:
        query = query.where(Application.created_at >= since)
    if until:
        query = query.where(Application.created_at < until)
    if after:
        query = query.where(_after(Application, after))
    result = await db.execute(
        query.order_by(Application.created_at.desc(), Application.id.desc()).limit(limit)
    )
    return [tuple(row) for row in result]


async def previews(
    db: AsyncSession,
    *,
    since: datetime,
    host: str | None,
    paid: bool,
    failed: bool,
    after: Cursor,
    limit: int,
) -> list[JobPreview]:
    query = select(JobPreview).where(JobPreview.created_at > since)
    if host:
        query = query.where(JobPreview.host == host)
    if paid:
        query = query.where(JobPreview.reader == "rendered")
    if failed:
        query = query.where(JobPreview.page.is_(None))
    if after:
        query = query.where(_after(JobPreview, after))
    result = await db.execute(
        query.order_by(JobPreview.created_at.desc(), JobPreview.id.desc()).limit(limit)
    )
    return list(result.scalars())


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


async def resume(db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID) -> ResumeFile | None:
    result = await db.execute(
        select(ResumeFile).where(ResumeFile.user_id == user_id, ResumeFile.id == resume_id)
    )
    return result.scalar_one_or_none()


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


def _nudge_recipients(quiet_since: datetime) -> Select[User, str | None]:
    """Users without the extension who have not been told about it lately, by
    this email or by the founder's note sent after their first sign-in.
    """
    emailed_lately = exists(
        select(OutreachEmail.id).where(
            OutreachEmail.user_id == User.id,
            OutreachEmail.kind.in_(("extension_nudge", "first_use_feedback")),
            OutreachEmail.status == "sent",
            OutreachEmail.created_at > quiet_since,
        )
    )
    return (
        select(User, Profile.full_name)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(_without_extension(), ~emailed_lately)
    )


async def count_nudge_recipients(db: AsyncSession, quiet_since: datetime) -> int:
    return await _count(db, cast_select(_nudge_recipients(quiet_since)))


async def nudge_recipients(db: AsyncSession, quiet_since: datetime, limit: int) -> list[Fields]:
    # Longest-standing accounts first: they have waited longest to hear about it.
    result = await db.execute(
        _nudge_recipients(quiet_since).order_by(User.created_at, User.id).limit(limit)
    )
    return [tuple(row) for row in result]


async def full_name(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    result = await db.execute(select(Profile.full_name).where(Profile.user_id == user_id))
    return result.scalar_one_or_none()


async def sent_lately(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> bool:
    result = await db.execute(
        select(
            exists(
                select(OutreachEmail.id).where(
                    OutreachEmail.user_id == user_id,
                    OutreachEmail.status == "sent",
                    OutreachEmail.created_at > since,
                )
            )
        )
    )
    return bool(result.scalar_one())


async def emails_for(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[OutreachEmail]:
    result = await db.execute(
        select(OutreachEmail)
        .where(OutreachEmail.user_id == user_id)
        .order_by(OutreachEmail.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
