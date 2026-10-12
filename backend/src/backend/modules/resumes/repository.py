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


async def count_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ResumeFile)
        .where(ResumeFile.user_id == user_id, ResumeFile.created_at > since)
    )
    return result.scalar_one()
