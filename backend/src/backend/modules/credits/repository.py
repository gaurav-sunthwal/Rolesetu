import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.credits.models import CreditUsage

# One statement, so checking and spending cannot be split by another request:
# the insert or the update only happens when the total stays within the limit.
# A concurrent spend waits on the row and is checked again against its new value.
_SPEND = text(
    """
    INSERT INTO credit_usage (user_id, period, used)
    SELECT CAST(:user_id AS uuid), CAST(:period AS date), CAST(:cost AS integer)
    WHERE CAST(:cost AS integer) <= CAST(:limit AS integer)
    ON CONFLICT (user_id, period) DO UPDATE
        SET used = credit_usage.used + EXCLUDED.used, updated_at = now()
        WHERE credit_usage.used + EXCLUDED.used <= CAST(:limit AS integer)
    RETURNING used
    """
)

_GIVE_BACK = text(
    """
    UPDATE credit_usage SET used = GREATEST(used - :cost, 0), updated_at = now()
    WHERE user_id = :user_id AND period = :period
    """
)


async def try_spend(
    db: AsyncSession, user_id: uuid.UUID, period: date, cost: int, limit: int
) -> int | None:
    """Credits used after spending `cost`, or None when that would pass `limit`."""
    result = await db.execute(
        _SPEND, {"user_id": user_id, "period": period, "cost": cost, "limit": limit}
    )
    used = result.scalar_one_or_none()
    return int(used) if used is not None else None


async def give_back(db: AsyncSession, user_id: uuid.UUID, period: date, cost: int) -> None:
    await db.execute(_GIVE_BACK, {"user_id": user_id, "period": period, "cost": cost})


async def used_in(db: AsyncSession, user_id: uuid.UUID, period: date) -> int:
    result = await db.execute(
        select(CreditUsage.used).where(CreditUsage.user_id == user_id, CreditUsage.period == period)
    )
    return int(result.scalar_one_or_none() or 0)
