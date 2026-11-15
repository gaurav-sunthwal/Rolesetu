import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.resumes.models import ResumeFile


async def get(db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID) -> ResumeFile | None:
    result = await db.execute(
        select(ResumeFile).where(ResumeFile.id == resume_id, ResumeFile.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_for_update(db: AsyncSession, resume_id: uuid.UUID) -> ResumeFile | None:
    """Unscoped: only the background enrichment uses it, for the resume it was
    started for."""
    result = await db.execute(
        select(ResumeFile).where(ResumeFile.id == resume_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def latest(db: AsyncSession, user_id: uuid.UUID) -> ResumeFile | None:
    result = await db.execute(
        select(ResumeFile)
        .where(ResumeFile.user_id == user_id)
        .order_by(ResumeFile.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[ResumeFile]:
    result = await db.execute(select(ResumeFile).where(ResumeFile.user_id == user_id))
    return list(result.scalars())


async def upload_counts(
    db: AsyncSession, user_id: uuid.UUID, hour_ago: datetime, day_ago: datetime
) -> tuple[int, int]:
    """Uploads in the last hour and the last day, in one query."""
    result = await db.execute(
        select(
            func.count().filter(ResumeFile.created_at > hour_ago),
            func.count().filter(ResumeFile.created_at > day_ago),
        ).where(ResumeFile.user_id == user_id)
    )
    hour, day = result.one()
    return int(hour), int(day)
