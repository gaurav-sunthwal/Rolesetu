"""Database reads and writes for the admin panel's billing pages. Unscoped by user
on purpose: only admin routes call these."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.billing.models import BillingAdminAction, BillingOrder, BillingPlan
from backend.modules.users.models import User


async def get_order(db: AsyncSession, order_id: uuid.UUID) -> BillingOrder | None:
    return await db.get(BillingOrder, order_id)


async def lock_order(db: AsyncSession, order_id: uuid.UUID) -> BillingOrder | None:
    result = await db.execute(
        select(BillingOrder)
        .where(BillingOrder.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def user_exists(db: AsyncSession, user_id: uuid.UUID) -> bool:
    return await db.get(User, user_id) is not None


async def orders_page(
    db: AsyncSession,
    *,
    status: str | None,
    grants: bool | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[tuple[BillingOrder, str]]:
    query = select(BillingOrder, User.email).join(User, User.id == BillingOrder.user_id)
    if status is not None:
        query = query.where(BillingOrder.status == status)
    if grants is not None:
        query = query.where((BillingOrder.amount == 0) if grants else (BillingOrder.amount > 0))
    if after is not None:
        created, row_id = after
        query = query.where(
            or_(
                BillingOrder.created_at < created,
                and_(BillingOrder.created_at == created, BillingOrder.id < row_id),
            )
        )
    rows = await db.execute(
        query.order_by(BillingOrder.created_at.desc(), BillingOrder.id.desc()).limit(limit)
    )
    return [(order, email) for order, email in rows.tuples()]


async def user_orders(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[BillingOrder, str]]:
    rows = await db.execute(
        select(BillingOrder, User.email)
        .join(User, User.id == BillingOrder.user_id)
        .where(BillingOrder.user_id == user_id)
        .order_by(BillingOrder.created_at.desc())
        .limit(200)
    )
    return [(order, email) for order, email in rows.tuples()]


async def actions(
    db: AsyncSession, user_id: uuid.UUID | None = None, limit: int = 30
) -> list[tuple[BillingAdminAction, str | None]]:
    query = select(BillingAdminAction, User.email).outerjoin(
        User, User.id == BillingAdminAction.user_id
    )
    if user_id is not None:
        query = query.where(BillingAdminAction.user_id == user_id)
    rows = await db.execute(query.order_by(BillingAdminAction.created_at.desc()).limit(limit))
    return [(action, email) for action, email in rows.tuples()]


async def plans(db: AsyncSession) -> dict[str, BillingPlan]:
    rows = await db.execute(select(BillingPlan))
    return {row.plan: row for row in rows.scalars()}


async def overview(db: AsyncSession, now: datetime, month_ago: datetime, week_on: datetime) -> Any:
    paid = BillingOrder.status == "paid"
    running = and_(paid, BillingOrder.pro_starts_at <= now, BillingOrder.pro_ends_at > now)
    users = BillingOrder.user_id
    # Each user's paid time ends at the latest end of their paid rows.
    ends = (
        select(users.label("user_id"), func.max(BillingOrder.pro_ends_at).label("until"))
        .where(paid)
        .group_by(users)
        .subquery()
    )
    totals = (
        await db.execute(
            select(
                func.count(distinct(users)).filter(running),
                func.count(distinct(users)).filter(and_(running, BillingOrder.amount > 0)),
                func.count(distinct(users)).filter(and_(running, BillingOrder.amount == 0)),
                func.coalesce(
                    func.sum(BillingOrder.amount).filter(
                        and_(paid, BillingOrder.paid_at >= month_ago)
                    ),
                    0,
                ),
                func.coalesce(func.sum(BillingOrder.amount).filter(paid), 0),
                func.coalesce(
                    func.sum(BillingOrder.amount).filter(BillingOrder.status == "refunded"), 0
                ),
                func.count().filter(
                    and_(BillingOrder.created_at >= month_ago, BillingOrder.amount > 0)
                ),
                func.count().filter(
                    and_(paid, BillingOrder.paid_at >= month_ago, BillingOrder.amount > 0)
                ),
            )
        )
    ).one()
    expiring = (
        await db.execute(
            select(func.count())
            .select_from(ends)
            .where(ends.c.until > now, ends.c.until <= week_on)
        )
    ).scalar_one()
    return (*totals, expiring)


def add_action(db: AsyncSession, **fields: Any) -> None:
    db.add(BillingAdminAction(id=uuid.uuid4(), **fields))
