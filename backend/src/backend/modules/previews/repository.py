from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.previews.models import JobPreview


async def find_fresh(db: AsyncSession, url_hash: str, read_after: datetime) -> JobPreview | None:
    """The newest successful read of this link, if it is recent enough to reuse."""
    result = await db.execute(
        select(JobPreview)
        .where(
            JobPreview.url_hash == url_hash,
            JobPreview.created_at > read_after,
            JobPreview.page.is_not(None),
        )
        .order_by(JobPreview.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_by_client(db: AsyncSession, client_hash: str, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(JobPreview)
        .where(JobPreview.client_hash == client_hash, JobPreview.created_at > since)
    )
    return result.scalar_one()


async def count_rendered(db: AsyncSession, since: datetime) -> int:
    """How many previews, from every visitor together, called the paid reader."""
    result = await db.execute(
        select(func.count())
        .select_from(JobPreview)
        .where(JobPreview.reader == "rendered", JobPreview.created_at > since)
    )
    return result.scalar_one()


async def delete_older_than(db: AsyncSession, cutoff: datetime) -> None:
    await db.execute(delete(JobPreview).where(JobPreview.created_at < cutoff))
