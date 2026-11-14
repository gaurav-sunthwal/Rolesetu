import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.billing.models import BillingOrder


async def lock_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Holds this user's billing lock until the transaction ends, so two payments
    settling at once (the checkout and the webhook, or two tabs) are worked out one
    after the other and never both start their month on the same day."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"billing:{user_id}"},
    )


async def add(db: AsyncSession, order: BillingOrder) -> None:
    db.add(order)
    await db.flush()


async def get_owned_for_update(
    db: AsyncSession, user_id: uuid.UUID, razorpay_order_id: str
) -> BillingOrder | None:
    result = await db.execute(
        select(BillingOrder)
        .where(BillingOrder.user_id == user_id, BillingOrder.razorpay_order_id == razorpay_order_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def owner_of(db: AsyncSession, razorpay_order_id: str) -> uuid.UUID | None:
    """Unscoped on purpose: only the signed webhook uses it, to learn which user
    paid; everything after that is scoped to that user."""
    result = await db.execute(
        select(BillingOrder.user_id).where(BillingOrder.razorpay_order_id == razorpay_order_id)
    )
    return result.scalar_one_or_none()


async def paid_orders(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[BillingOrder]:
    """The user's paid months, latest ending first. Everything the plan shows (Pro
    or not, until when, the payments list) is worked out from this one query."""
    result = await db.execute(
        select(BillingOrder)
        .where(BillingOrder.user_id == user_id, BillingOrder.status == "paid")
        .order_by(BillingOrder.pro_ends_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def order_checks(
    db: AsyncSession, user_id: uuid.UUID, since: datetime
) -> tuple[int, datetime | None]:
    """Orders started since `since`, and when the paid time ends, in one query."""
    result = await db.execute(
        select(
            func.count().filter(BillingOrder.created_at >= since),
            func.max(BillingOrder.pro_ends_at).filter(BillingOrder.status == "paid"),
        ).where(BillingOrder.user_id == user_id)
    )
    started, until = result.one()
    return int(started), until


async def is_pro_at(db: AsyncSession, user_id: uuid.UUID, moment: datetime) -> bool:
    result = await db.execute(
        select(BillingOrder.id)
        .where(
            BillingOrder.user_id == user_id,
            BillingOrder.status == "paid",
            BillingOrder.pro_starts_at <= moment,
            BillingOrder.pro_ends_at > moment,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
