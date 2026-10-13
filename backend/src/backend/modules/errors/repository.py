from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.errors.models import ErrorEvent

Fields = tuple[Any, ...]


async def count_for(db: AsyncSession, fingerprint: str, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ErrorEvent)
        .where(ErrorEvent.fingerprint == fingerprint, ErrorEvent.created_at > since)
    )
    return result.scalar_one()


async def delete_older_than(db: AsyncSession, cutoff: datetime) -> None:
    await db.execute(delete(ErrorEvent).where(ErrorEvent.created_at < cutoff))


async def groups(db: AsyncSession, *, since: datetime, source: str | None) -> list[Fields]:
    """Events grouped into problems, the most frequent first: (latest event,
    how many, first seen, last seen).
    """
    counted = (
        select(
            ErrorEvent.fingerprint,
            func.count().label("events"),
            func.min(ErrorEvent.created_at).label("first_at"),
            func.max(ErrorEvent.created_at).label("last_at"),
        )
        .where(ErrorEvent.created_at > since)
        .group_by(ErrorEvent.fingerprint)
    )
    if source:
        counted = counted.where(ErrorEvent.source == source)
    totals = counted.subquery()
    result = await db.execute(
        select(ErrorEvent, totals.c.events, totals.c.first_at, totals.c.last_at)
        .join(
            totals,
            and_(
                ErrorEvent.fingerprint == totals.c.fingerprint,
                ErrorEvent.created_at == totals.c.last_at,
            ),
        )
        .order_by(totals.c.events.desc(), totals.c.last_at.desc())
        .limit(200)
    )
    return [tuple(row) for row in result]


async def counts_by_source(db: AsyncSession, since: datetime) -> dict[str, int]:
    result = await db.execute(
        select(ErrorEvent.source, func.count())
        .where(ErrorEvent.created_at > since)
        .group_by(ErrorEvent.source)
    )
    return {source: count for source, count in result}


async def count_since(db: AsyncSession, since: datetime) -> int:
    result = await db.execute(
        select(func.count()).select_from(ErrorEvent).where(ErrorEvent.created_at > since)
    )
    return result.scalar_one()


async def events_for(db: AsyncSession, fingerprint: str, limit: int) -> list[ErrorEvent]:
    result = await db.execute(
        select(ErrorEvent)
        .where(ErrorEvent.fingerprint == fingerprint)
        .order_by(ErrorEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def delete_group(db: AsyncSession, fingerprint: str) -> int:
    result = await db.execute(delete(ErrorEvent).where(ErrorEvent.fingerprint == fingerprint))
    return result.rowcount if isinstance(result, CursorResult) else 0
