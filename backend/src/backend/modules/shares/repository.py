import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.shares.models import MatchShare


async def get_for_match(
    db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID
) -> MatchShare | None:
    result = await db.execute(
        select(MatchShare).where(MatchShare.user_id == user_id, MatchShare.match_id == match_id)
    )
    return result.scalar_one_or_none()


async def get_by_slug(db: AsyncSession, slug: str) -> MatchShare | None:
    """Unscoped on purpose: a share is public to anyone who has its link."""
    result = await db.execute(select(MatchShare).where(MatchShare.slug == slug))
    return result.scalar_one_or_none()


async def count_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(MatchShare)
        .where(MatchShare.user_id == user_id, MatchShare.created_at >= since)
    )
    return int(result.scalar_one())


async def delete_owned(db: AsyncSession, user_id: uuid.UUID, slug: str) -> bool:
    result = await db.execute(
        delete(MatchShare).where(MatchShare.user_id == user_id, MatchShare.slug == slug)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]
