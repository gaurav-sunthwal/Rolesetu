import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.modules.matches.models import Job, Match


async def get(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> Match | None:
    result = await db.execute(
        select(Match)
        .where(Match.id == match_id, Match.user_id == user_id)
        .options(selectinload(Match.job))
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, match_id: uuid.UUID) -> Match | None:
    """Unscoped lookup for the background runner, which only ever receives ids
    the API created itself. Never call this from a route.
    """
    result = await db.execute(
        select(Match).where(Match.id == match_id).options(selectinload(Match.job))
    )
    return result.scalar_one_or_none()


async def find_job(db: AsyncSession, user_id: uuid.UUID, content_hash: str) -> Job | None:
    result = await db.execute(
        select(Job)
        .where(Job.user_id == user_id, Job.content_hash == content_hash)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def find_job_by_url(
    db: AsyncSession, user_id: uuid.UUID, url: str, fetched_after: datetime
) -> Job | None:
    """A job already read from this link recently, so the page is not fetched again."""
    result = await db.execute(
        select(Job)
        .where(Job.user_id == user_id, Job.url == url, Job.created_at > fetched_after)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_rendered_reads(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    """How many of this user's jobs were read through the paid page reader."""
    result = await db.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.user_id == user_id,
            Job.created_at > since,
            Job.job_json["listing"]["reader"].astext == "rendered",
        )
    )
    return result.scalar_one()


async def find_reusable(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    profile_version: int,
    engine_version: str,
    fresh_after: datetime,
) -> Match | None:
    """A finished result for this job and profile version, or one still running."""
    result = await db.execute(
        select(Match)
        .where(
            Match.user_id == user_id,
            Match.job_id == job_id,
            Match.profile_version == profile_version,
            or_(
                # A result from older scoring rules is not reused.
                and_(Match.status == "completed", Match.prompt_versions == engine_version),
                and_(Match.status == "pending", Match.created_at > fresh_after),
            ),
        )
        .options(selectinload(Match.job))
        .order_by(Match.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Match)
        .where(Match.user_id == user_id, Match.created_at > since)
    )
    return result.scalar_one()


async def list_page(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Match]:
    query = select(Match).where(Match.user_id == user_id).options(selectinload(Match.job))
    if after:
        created_at, row_id = after
        query = query.where(
            or_(
                Match.created_at < created_at,
                and_(Match.created_at == created_at, Match.id < row_id),
            )
        )
    query = query.order_by(Match.created_at.desc(), Match.id.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars())
