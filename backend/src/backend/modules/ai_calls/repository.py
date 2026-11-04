import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.ai_calls.models import AiCall
from backend.modules.users.models import User

Cursor = tuple[datetime, uuid.UUID] | None


async def delete_older_than(db: AsyncSession, cutoff: datetime) -> None:
    await db.execute(delete(AiCall).where(AiCall.created_at < cutoff))


async def list_calls(
    db: AsyncSession,
    *,
    since: datetime,
    source: str | None,
    user_id: uuid.UUID | None,
    after: Cursor,
    limit: int,
) -> list[tuple[AiCall, str | None]]:
    """Newest first, each with the email of the user it was made for."""
    query = (
        select(AiCall, User.email)
        .outerjoin(User, User.id == AiCall.user_id)
        .where(AiCall.created_at > since)
    )
    if source:
        query = query.where(AiCall.source == source)
    if user_id:
        query = query.where(AiCall.user_id == user_id)
    if after:
        created_at, row_id = after
        query = query.where(
            or_(
                AiCall.created_at < created_at,
                and_(AiCall.created_at == created_at, AiCall.id < row_id),
            )
        )
    result = await db.execute(
        query.order_by(AiCall.created_at.desc(), AiCall.id.desc()).limit(limit)
    )
    return [(call, email) for call, email in result.tuples()]


async def summary(db: AsyncSession, since: datetime) -> dict[str, Any]:
    """Totals for the period, and how many calls came from each source, in one query."""
    result = await db.execute(
        select(
            AiCall.source,
            func.count(),
            func.count().filter(~AiCall.ok),
            func.count().filter(AiCall.own_key),
            func.coalesce(func.sum(AiCall.input_tokens), 0),
            func.coalesce(func.sum(AiCall.output_tokens), 0),
        )
        .where(AiCall.created_at > since)
        .group_by(AiCall.source)
    )
    found: dict[str, Any] = {
        "total": 0,
        "failed": 0,
        "own_key": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "by_source": {},
    }
    for source, calls, failed, own_key, input_tokens, output_tokens in result.tuples():
        found["by_source"][source] = calls
        found["total"] += calls
        found["failed"] += failed
        found["own_key"] += own_key
        found["input_tokens"] += input_tokens or 0
        found["output_tokens"] += output_tokens or 0
    return found
