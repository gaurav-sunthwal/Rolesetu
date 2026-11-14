import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.billing.models import (
    LIVE_SUBSCRIPTION_STATES,
    BillingOrder,
    BillingSubscription,
    RazorpayPlan,
)


async def plan_id_for(db: AsyncSession, amount: int, currency: str) -> str | None:
    result = await db.execute(
        select(RazorpayPlan.razorpay_plan_id).where(
            RazorpayPlan.amount == amount, RazorpayPlan.currency == currency
        )
    )
    return result.scalar_one_or_none()


async def save_plan(db: AsyncSession, plan_id: str, amount: int, currency: str) -> str:
    """Keeps the plan for this price, or the one saved first if two were made at once."""
    await db.execute(
        insert(RazorpayPlan)
        .values(razorpay_plan_id=plan_id, amount=amount, currency=currency)
        .on_conflict_do_nothing()
    )
    saved = await plan_id_for(db, amount, currency)
    return saved or plan_id


async def latest_live(db: AsyncSession, user_id: uuid.UUID) -> BillingSubscription | None:
    """The user's newest subscription that can still charge, locked."""
    result = await db.execute(
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == user_id,
            BillingSubscription.status.in_(LIVE_SUBSCRIPTION_STATES),
        )
        .order_by(BillingSubscription.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def all_live(db: AsyncSession, user_id: uuid.UUID) -> list[BillingSubscription]:
    result = await db.execute(
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == user_id,
            BillingSubscription.status.in_(LIVE_SUBSCRIPTION_STATES),
        )
        .with_for_update()
    )
    return list(result.scalars())


async def latest(db: AsyncSession, user_id: uuid.UUID) -> BillingSubscription | None:
    """The user's newest subscription in any state, for showing it."""
    result = await db.execute(
        select(BillingSubscription)
        .where(BillingSubscription.user_id == user_id)
        .order_by(BillingSubscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_owned_for_update(
    db: AsyncSession, user_id: uuid.UUID, razorpay_subscription_id: str
) -> BillingSubscription | None:
    result = await db.execute(
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == user_id,
            BillingSubscription.razorpay_subscription_id == razorpay_subscription_id,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def owner_of(db: AsyncSession, razorpay_subscription_id: str) -> uuid.UUID | None:
    """Unscoped on purpose: only the signed webhook uses it, to learn whose it is."""
    result = await db.execute(
        select(BillingSubscription.user_id).where(
            BillingSubscription.razorpay_subscription_id == razorpay_subscription_id
        )
    )
    return result.scalar_one_or_none()


async def started_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(BillingSubscription)
        .where(BillingSubscription.user_id == user_id, BillingSubscription.created_at >= since)
    )
    return int(result.scalar_one())


async def order_for_payment(db: AsyncSession, payment_id: str) -> BillingOrder | None:
    result = await db.execute(
        select(BillingOrder).where(BillingOrder.razorpay_payment_id == payment_id)
    )
    return result.scalar_one_or_none()


async def charges_of(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    """Paid charges since `since`, to know whether a charge is a subscription's first."""
    result = await db.execute(
        select(func.count())
        .select_from(BillingOrder)
        .where(
            BillingOrder.user_id == user_id,
            BillingOrder.status == "paid",
            BillingOrder.paid_at >= since,
            BillingOrder.amount > 0,
        )
    )
    return int(result.scalar_one())
