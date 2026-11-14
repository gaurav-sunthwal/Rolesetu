"""What an admin can do about payments and Pro, and the figures the panel shows.

- Give Pro for some days (a "grant": a paid row of ₹0, so everything that reads Pro
  from paid rows keeps working unchanged).
- Refund a payment through Razorpay, which ends the Pro it bought.
- Remove one month (paid or given) without a refund, or end someone's Pro outright.
- Change a plan's price, length and whether it is on sale.

Every change is logged with the admin and a reason. After anything is taken away,
months that had not started yet move up, so nobody loses time they paid for.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.exceptions import ConflictError, NotFoundError, UnavailableError
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.modules.billing import admin_repository as repo
from backend.modules.billing import prices, razorpay, repository, subscriptions
from backend.modules.billing.admin_schemas import (
    BillingActionRead,
    BillingOverview,
    GrantWrite,
    OrderAdminRead,
    OrderStatus,
    PlanAdminRead,
    PlanWrite,
    UserBillingAdmin,
)
from backend.modules.billing.models import BillingAdminAction, BillingOrder, BillingPlan
from backend.modules.referrals import service as referrals

logger = logging.getLogger(__name__)

GRANT_PLAN = "pro_grant"
_ALL_PAID = 500


def _razorpay_url(order: BillingOrder) -> str | None:
    if order.razorpay_payment_id:
        return f"https://dashboard.razorpay.com/app/payments/{order.razorpay_payment_id}"
    return None


def order_read(order: BillingOrder, email: str) -> OrderAdminRead:
    grant = order.amount == 0
    return OrderAdminRead(
        id=order.id,
        user_id=order.user_id,
        user_email=email,
        plan=order.plan,
        kind="grant" if grant else "payment",
        amount=order.amount,
        currency=order.currency,
        status=cast(OrderStatus, order.status),
        razorpay_order_id=None if grant else order.razorpay_order_id,
        razorpay_payment_id=order.razorpay_payment_id,
        created_at=order.created_at,
        paid_at=order.paid_at,
        pro_starts_at=order.pro_starts_at,
        pro_ends_at=order.pro_ends_at,
        refunded_at=order.refunded_at,
        refund_id=order.refund_id,
        note=order.note,
        razorpay_url=_razorpay_url(order),
    )


def _action_read(action: BillingAdminAction, email: str | None) -> BillingActionRead:
    return BillingActionRead(
        id=action.id,
        created_at=action.created_at,
        action=action.action,
        admin_email=action.admin_email,
        user_id=action.user_id,
        user_email=email,
        order_id=action.order_id,
        note=action.note,
        amount=action.amount,
        days=action.days,
    )


def restack(paid: list[BillingOrder], now: datetime) -> None:
    """Moves months that have not started yet up behind the paid time still running,
    keeping each one's length. Called after a month is refunded or removed, so the
    ones bought after it do not leave a gap. Months already running stay as they are."""
    started = [o for o in paid if o.pro_starts_at and o.pro_ends_at and o.pro_starts_at <= now]
    waiting = sorted(
        (o for o in paid if o.pro_starts_at and o.pro_ends_at and o.pro_starts_at > now),
        key=lambda o: o.pro_starts_at or now,
    )
    anchor = max((o.pro_ends_at for o in started if o.pro_ends_at), default=now)
    anchor = max(anchor, now)
    for order in waiting:
        assert order.pro_starts_at and order.pro_ends_at
        length = order.pro_ends_at - order.pro_starts_at
        order.pro_starts_at, order.pro_ends_at = anchor, anchor + length
        anchor = order.pro_ends_at


async def _restack_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    restack(await repository.paid_orders(db, user_id, _ALL_PAID), datetime.now(UTC))


async def _locked(db: AsyncSession, order_id: uuid.UUID) -> BillingOrder:
    """The order, under its user's billing lock (the same one payments take) and its
    row lock, so an admin change and a payment settling never overlap."""
    found = await repo.get_order(db, order_id)
    if found is None:
        raise NotFoundError("That payment was not found.")
    await repository.lock_user(db, found.user_id)
    order = await repo.lock_order(db, order_id)
    if order is None:
        raise NotFoundError("That payment was not found.")
    return order


async def _read(db: AsyncSession, order: BillingOrder) -> OrderAdminRead:
    rows = await repo.user_orders(db, order.user_id)
    email = rows[0][1] if rows else ""
    return order_read(order, email)


# ── Figures ───────────────────────────────────────────────────────────────────


def _plan_read(plan: str, row: BillingPlan | None) -> PlanAdminRead:
    default = prices.DEFAULTS[plan]
    return PlanAdminRead(
        plan=plan,
        description=row.description if row else default.description,
        amount=row.amount if row else default.amount,
        currency=row.currency if row else default.currency,
        days=row.days if row else default.days,
        active=row.active if row else True,
        updated_by=row.updated_by if row else None,
        updated_at=row.updated_at if row else None,
    )


def _plan_reads(rows: dict[str, BillingPlan]) -> list[PlanAdminRead]:
    return [_plan_read(plan, rows.get(plan)) for plan in prices.DEFAULTS]


async def overview(db: AsyncSession) -> BillingOverview:
    now = datetime.now(UTC)
    (
        pro_now,
        paying_now,
        granted_now,
        revenue_30d,
        revenue_total,
        refunded_total,
        orders_30d,
        paid_30d,
        expiring,
    ) = await repo.overview(db, now, now - timedelta(days=30), now + timedelta(days=7))
    return BillingOverview(
        payments_enabled=razorpay.keys() is not None,
        webhook_enabled=bool(get_settings().razorpay_webhook_secret),
        plans=_plan_reads(await repo.plans(db)),
        pro_now=pro_now,
        paying_now=paying_now,
        granted_now=granted_now,
        expiring_7d=expiring,
        currency="INR",
        revenue_30d=int(revenue_30d),
        revenue_total=int(revenue_total),
        refunded_total=int(refunded_total),
        orders_30d=orders_30d,
        paid_30d=paid_30d,
        recent_actions=[_action_read(a, e) for a, e in await repo.actions(db, limit=20)],
    )


async def list_orders(
    db: AsyncSession, *, status: str | None, kind: str | None, cursor: str | None, limit: int
) -> Page[OrderAdminRead]:
    rows = await repo.orders_page(
        db,
        status=status,
        grants=None if kind is None else kind == "grant",
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    shown = rows[:limit]
    last = shown[-1][0] if len(rows) > limit and shown else None
    return Page[OrderAdminRead](
        items=[order_read(order, email) for order, email in shown],
        next_cursor=encode_cursor(last.created_at, last.id) if last else None,
    )


async def user_billing(db: AsyncSession, user_id: uuid.UUID) -> UserBillingAdmin:
    if not await repo.user_exists(db, user_id):
        raise NotFoundError("User not found.")
    now = datetime.now(UTC)
    rows = await repo.user_orders(db, user_id)
    paid = [order for order, _ in rows if order.status == "paid"]
    pro = any(
        o.pro_starts_at and o.pro_ends_at and o.pro_starts_at <= now < o.pro_ends_at for o in paid
    )
    until = max((o.pro_ends_at for o in paid if o.pro_ends_at), default=None)
    return UserBillingAdmin(
        plan="pro" if pro else "free",
        pro_until=until if until and until > now else None,
        orders=[order_read(order, email) for order, email in rows],
        actions=[_action_read(a, e) for a, e in await repo.actions(db, user_id=user_id)],
    )


# ── Changes ───────────────────────────────────────────────────────────────────


async def grant(
    db: AsyncSession, *, admin_email: str, user_id: uuid.UUID, body: GrantWrite
) -> OrderAdminRead:
    """Gives Pro for `days`, after any paid time already bought."""
    if not await repo.user_exists(db, user_id):
        raise NotFoundError("User not found.")
    await repository.lock_user(db, user_id)
    now = datetime.now(UTC)
    paid = await repository.paid_orders(db, user_id, _ALL_PAID)
    until = max((o.pro_ends_at for o in paid if o.pro_ends_at), default=None)
    starts = until if until and until > now else now
    row_id = uuid.uuid4()
    order = BillingOrder(
        id=row_id,
        user_id=user_id,
        razorpay_order_id=f"grant_{row_id.hex}",
        plan=GRANT_PLAN,
        amount=0,
        currency="INR",
        status="paid",
        paid_at=now,
        pro_starts_at=starts,
        pro_ends_at=starts + timedelta(days=body.days),
        days=body.days,
        note=body.note,
    )
    await repository.add(db, order)
    repo.add_action(
        db,
        user_id=user_id,
        order_id=order.id,
        action="grant",
        admin_email=admin_email,
        note=body.note,
        days=body.days,
    )
    logger.info("Admin %s gave user %s %s days of Pro", admin_email, user_id, body.days)
    return await _read(db, order)


async def refund(
    db: AsyncSession, *, admin_email: str, order_id: uuid.UUID, note: str
) -> OrderAdminRead:
    """Refunds a payment in full through Razorpay and ends the Pro it bought.

    The order stays locked for the whole call, so a second click waits and then
    finds it refunded. If Razorpay's answer is lost, the payment is read back: a
    refund that went through is recorded, never asked for again.
    """
    order = await _locked(db, order_id)
    if order.status == "refunded":
        return await _read(db, order)
    if order.status != "paid" or order.amount == 0 or not order.razorpay_payment_id:
        raise ConflictError("Only a paid payment can be refunded. Remove a given month instead.")
    # A refund means they should not be charged again: autopay stops first, so if
    # Razorpay cannot be reached nothing has happened yet.
    await subscriptions.stop_all(db, user_id=order.user_id, reason="admin_refund")

    refund_id: str | None = None
    try:
        made = await razorpay.refund_payment(
            order.razorpay_payment_id, amount=order.amount, key=f"refund-{order.id}"
        )
        refund_id = str(made.get("id")) if made.get("id") else None
    except (httpx.HTTPError, razorpay.RazorpayError) as error:
        logger.warning("Refund for order %s did not answer cleanly: %s", order.id, error)
        payment = await razorpay.fetch_payment(order.razorpay_payment_id)
        if int(payment.get("amount_refunded") or 0) < order.amount:
            raise UnavailableError(
                "Razorpay did not make the refund, so nothing was refunded and Pro is"
                " unchanged. Try again, or refund it in the Razorpay dashboard."
            ) from error

    now = datetime.now(UTC)
    order.status = "refunded"
    order.refunded_at = now
    order.refund_id = refund_id
    order.note = note
    await _restack_user(db, order.user_id)
    # A month paid with a friend's referral reward gives the reward back.
    await referrals.release(db, order_id=order.id)
    repo.add_action(
        db,
        user_id=order.user_id,
        order_id=order.id,
        action="refund",
        admin_email=admin_email,
        note=note,
        amount=order.amount,
    )
    logger.info("Admin %s refunded order %s", admin_email, order.id)
    return await _read(db, order)


async def revoke(
    db: AsyncSession, *, admin_email: str, order_id: uuid.UUID, note: str
) -> OrderAdminRead:
    """Takes away the Pro one row gave, without a refund."""
    order = await _locked(db, order_id)
    if order.status == "revoked":
        return await _read(db, order)
    if order.status != "paid":
        raise ConflictError("Only an active or upcoming month can be removed.")
    await subscriptions.stop_all(db, user_id=order.user_id, reason="admin_revoke")
    order.status = "revoked"
    order.note = note
    await _restack_user(db, order.user_id)
    repo.add_action(
        db,
        user_id=order.user_id,
        order_id=order.id,
        action="revoke",
        admin_email=admin_email,
        note=note,
        amount=order.amount,
        days=order.days,
    )
    return await _read(db, order)


async def end_pro(
    db: AsyncSession, *, admin_email: str, user_id: uuid.UUID, note: str
) -> UserBillingAdmin:
    """Ends someone's Pro now: every month running or still to come is removed,
    without refunds."""
    if not await repo.user_exists(db, user_id):
        raise NotFoundError("User not found.")
    await repository.lock_user(db, user_id)
    await subscriptions.stop_all(db, user_id=user_id, reason="admin_end_pro")
    now = datetime.now(UTC)
    ended = 0
    for order in await repository.paid_orders(db, user_id, _ALL_PAID):
        if order.pro_ends_at and order.pro_ends_at > now:
            order.status = "revoked"
            order.note = note
            ended += 1
    if ended == 0:
        raise ConflictError("This user has no Pro to end.")
    repo.add_action(
        db, user_id=user_id, action="end_pro", admin_email=admin_email, note=note, days=None
    )
    await db.flush()
    return await user_billing(db, user_id)


async def update_plan(
    db: AsyncSession, *, admin_email: str, plan: str, body: PlanWrite
) -> PlanAdminRead:
    """Changes what a plan costs from the next order on. Paid orders keep theirs."""
    if plan not in prices.DEFAULTS:
        raise NotFoundError("That plan does not exist.")
    row = await db.get(BillingPlan, plan)
    if row is None:
        row = BillingPlan(plan=plan, currency=prices.DEFAULTS[plan].currency)
        db.add(row)
    row.description = body.description
    row.amount = body.amount
    row.days = body.days
    row.active = body.active
    row.updated_by = admin_email
    await db.flush()
    await db.refresh(row)
    repo.add_action(
        db,
        action="price",
        admin_email=admin_email,
        note=body.note or ("On sale" if body.active else "Taken off sale"),
        amount=body.amount,
        days=body.days,
    )
    return _plan_read(plan, row)
