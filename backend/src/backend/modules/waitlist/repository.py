from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.waitlist.models import WaitlistEntry


async def add_if_new(db: AsyncSession, email: str, client_hash: str) -> None:
    """Adds the address. One already on the list is left as it is."""
    await db.execute(
        insert(WaitlistEntry)
        .values(email=email, client_hash=client_hash)
        .on_conflict_do_nothing(index_elements=[WaitlistEntry.email])
    )


async def count_by_client(db: AsyncSession, client_hash: str, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(WaitlistEntry)
        .where(WaitlistEntry.client_hash == client_hash, WaitlistEntry.created_at > since)
    )
    return result.scalar_one()
