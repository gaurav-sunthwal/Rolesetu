"""Buying Pro with Razorpay's standard checkout (one month per payment, no autopay).

How a payment becomes Pro, and why each step is there:

1. `create_order`: the server makes the Razorpay order with the price from
   `plans.py`. The browser never sends an amount.
2. The user pays in Razorpay's window. The window hands the browser a payment id
   and a signature.
3. `verify_payment`: the signature must match (HMAC with the key secret, which only
   the server has). Then the server asks Razorpay for that payment and checks it is
   captured, for this order, for the full amount and currency. Only then is the
   order marked paid.
4. `handle_webhook`: the same settling, started by Razorpay itself, for when the
   browser closed before step 3. Either path may run first; the other finds the
   order already paid and does nothing.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
)
from backend.modules.billing import prices, razorpay, repository
from backend.modules.billing.models import BillingOrder
from backend.modules.billing.plans import PRO_MONTH, REFERRAL_AMOUNT, RENEW_WITHIN_DAYS, Price
from backend.modules.billing.schemas import (
    OrderRead,
    PaymentRead,
    PaymentVerify,
    PlanRead,
    PriceRead,
    WebhookEvent,
)
from backend.modules.referrals import service as referrals

logger = logging.getLogger(__name__)

MAX_ORDERS_PER_HOUR = 10
_PAYMENTS_SHOWN = 12


def _price(plan: str) -> Price:
    return prices.DEFAULTS[plan]


async def is_pro(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    """Whether the user has paid for right now. Plan limits read this."""
    return await repository.is_pro_at(db, user_id, datetime.now(UTC))


def _renew_from(until: datetime | None, now: datetime) -> datetime | None:
    if until is None:
        return None
    opens = until - timedelta(days=RENEW_WITHIN_DAYS)
    return opens if opens > now else None


# Enough to cover every month bought ahead; only the newest are listed.
_PAID_READ = 50


def _referral_price(price: Price) -> Price:
    """The price of a month paid with a referral reward (INR only)."""
    if price.currency != "INR":
        return price
    return replace(price, amount=min(price.amount, REFERRAL_AMOUNT))


def _plan_from(
    paid: list[BillingOrder], now: datetime, price: Price, *, referral: bool = False
) -> PlanRead:
    """The plan, from the user's paid orders (latest ending first) and the price on
    sale now. No queries."""
    if referral:
        price = _referral_price(price)
    until = max((order.pro_ends_at for order in paid if order.pro_ends_at), default=None)
    pro = any(
        order.pro_starts_at and order.pro_ends_at and order.pro_starts_at <= now < order.pro_ends_at
        for order in paid
    )
    shown = sorted(
        (order for order in paid if order.paid_at and order.pro_starts_at and order.pro_ends_at),
        key=lambda order: order.paid_at or now,
        reverse=True,
    )[:_PAYMENTS_SHOWN]
    return PlanRead(
        plan="pro" if pro else "free",
        pro_until=until if until and until > now else None,
        renew_from=_renew_from(until, now),
        payments_enabled=razorpay.keys() is not None,
        price=PriceRead(
            plan=price.plan, amount=price.amount, currency=price.currency, days=price.days
        ),
        referral_price=referral and price.currency == "INR",
        payments=[
            PaymentRead(
                amount=order.amount,
                currency=order.currency,
                paid_at=order.paid_at,
                pro_starts_at=order.pro_starts_at,
                pro_ends_at=order.pro_ends_at,
            )
            for order in shown
            # Months an admin gave for free are not payments.
            if order.paid_at and order.pro_starts_at and order.pro_ends_at and order.amount > 0
        ],
    )


async def get_plan(db: AsyncSession, *, user_id: uuid.UUID) -> PlanRead:
    # Someone looking at their plan may be about to pay: open the connection now,
    # so the payment does not wait for it.
    razorpay.warm_up()
    paid = await repository.paid_orders(db, user_id, _PAID_READ)
    price, _ = await prices.current_price(db, PRO_MONTH.plan)
    referral = await referrals.has_reward(db, user_id=user_id)
    return _plan_from(paid, datetime.now(UTC), price, referral=referral)


def _day(moment: datetime) -> str:
    return f"{moment.day} {moment:%b %Y}"


async def create_order(db: AsyncSession, *, user_id: uuid.UUID, email: str, plan: str) -> OrderRead:
    found_keys = razorpay.require_keys()
    price, on_sale = await prices.current_price(db, plan)
    if not on_sale:
        raise UnavailableError("Pro is not on sale right now. Nothing was charged.")
    now = datetime.now(UTC)

    started, until = await repository.order_checks(db, user_id, now - timedelta(hours=1))
    if started >= MAX_ORDERS_PER_HOUR:
        raise RateLimitedError(
            "You have started a lot of payments in the last hour. Please wait a little and"
            " try again."
        )
    if (opens := _renew_from(until, now)) is not None and until is not None:
        raise ConflictError(
            f"You already have Pro until {_day(until)}. You can buy the next month from"
            f" {_day(opens)}."
        )

    # A friend's referral reward, if any, makes this month cheaper. Held locked
    # until this request ends, so two orders at once cannot both use it.
    reward = await referrals.find_reward(db, user_id=user_id) if price.currency == "INR" else None
    if reward is not None:
        price = _referral_price(price)

    row_id = uuid.uuid4()
    made = await razorpay.create_order(
        amount=price.amount,
        currency=price.currency,
        receipt=str(row_id),
        notes={
            "user_id": str(user_id),
            "plan": price.plan,
            "referral": "yes" if reward is not None else "no",
        },
    )
    order_id = made.get("id")
    if (
        not isinstance(order_id, str)
        or not order_id.startswith("order_")
        or made.get("amount") != price.amount
        or made.get("currency") != price.currency
    ):
        logger.error("Razorpay made an order that does not match what was asked for")
        raise UnavailableError(
            "Payments are not available right now. Nothing was charged. Please try again soon."
        )

    await repository.add(
        db,
        BillingOrder(
            id=row_id,
            user_id=user_id,
            razorpay_order_id=order_id,
            plan=price.plan,
            amount=price.amount,
            currency=price.currency,
            status="created",
            days=price.days,
        ),
    )
    if reward is not None:
        # After the order exists: the reward points at it. Spent only once it is paid.
        referrals.set_aside(reward, order_id=row_id)
    return OrderRead(
        order_id=order_id,
        amount=price.amount,
        currency=price.currency,
        key_id=found_keys.key_id,
        name="Rolesetu",
        description=price.description,
        email=email,
    )


class _NotPaid(Exception):
    """The payment exists but did not pay for this order."""


async def _confirmed(order: BillingOrder, payment: dict[str, Any]) -> None:
    """Passes only if Razorpay's record shows this order paid in full and captured."""
    if (
        payment.get("order_id") != order.razorpay_order_id
        or payment.get("amount") != order.amount
        or payment.get("currency") != order.currency
    ):
        raise _NotPaid("payment does not belong to this order")
    if payment.get("status") == "authorized":
        payment = await razorpay.capture_payment(
            str(payment.get("id")), amount=order.amount, currency=order.currency
        )
    if payment.get("status") != "captured":
        raise _NotPaid(f"payment status is {payment.get('status')}")


def _settle(order: BillingOrder, payment_id: str, paid: list[BillingOrder]) -> list[BillingOrder]:
    """Marks a confirmed order paid with its month of Pro, starting when the paid
    time already bought ends. Returns the paid orders including this one. The
    caller holds the user's billing lock and the order's row lock; the change is
    written when the request's transaction commits."""
    now = datetime.now(UTC)
    until = max((o.pro_ends_at for o in paid if o.pro_ends_at), default=None)
    starts = until if until and until > now else now
    order.status = "paid"
    order.razorpay_payment_id = payment_id
    order.paid_at = now
    order.pro_starts_at = starts
    order.pro_ends_at = starts + timedelta(days=order.days or _price(order.plan).days)
    logger.info("Order %s paid; Pro until %s", order.id, order.pro_ends_at.isoformat())
    return [order, *paid]


def _drop(task: "asyncio.Task[Any]") -> None:
    """Stops a Razorpay read that is no longer needed, without leaving an
    unread error behind."""
    if not task.done():
        task.cancel()
    elif not task.cancelled():
        task.exception()


async def _locked_order(
    db: AsyncSession, user_id: uuid.UUID, razorpay_order_id: str
) -> tuple[BillingOrder | None, list[BillingOrder]]:
    """The order under the user's billing lock, and their paid orders."""
    await repository.lock_user(db, user_id)
    order = await repository.get_owned_for_update(db, user_id, razorpay_order_id)
    paid = await repository.paid_orders(db, user_id, _PAID_READ) if order else []
    return order, paid


async def verify_payment(
    db: AsyncSession, *, user_id: uuid.UUID, payload: PaymentVerify
) -> PlanRead:
    found_keys = razorpay.require_keys()
    # Checked before anything is read, so a forged request costs one hash and
    # never reaches Razorpay or the database.
    if not razorpay.payment_signature_ok(
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
        secret=found_keys.key_secret,
    ):
        logger.warning("Payment signature did not match for user %s", user_id)
        raise BadRequestError(
            "We could not confirm this payment. If money left your account, it is refunded"
            " by Razorpay automatically; otherwise please try again."
        )

    # Razorpay is asked while the database is read: the two waits overlap.
    asking = asyncio.create_task(razorpay.fetch_payment(payload.razorpay_payment_id))
    try:
        # Scoped to the caller: someone else's order is "not found", whatever its id.
        order, paid = await _locked_order(db, user_id, payload.razorpay_order_id)
        if order is None:
            raise NotFoundError("That payment was not found. Please start the upgrade again.")
        price, _ = await prices.current_price(db, PRO_MONTH.plan)
        if order.status == "paid":
            if order.razorpay_payment_id == payload.razorpay_payment_id:
                return _plan_from(paid, datetime.now(UTC), price)  # the webhook got here first
            raise ConflictError("This order is already paid.")
        payment = await asking
    finally:
        _drop(asking)

    try:
        await _confirmed(order, payment)
    except _NotPaid as reason:
        logger.warning("Order %s not settled: %s", order.id, reason)
        raise BadRequestError(
            "Razorpay has not confirmed this payment. If you were charged, Pro turns on by"
            " itself within a few minutes; otherwise please try again."
        ) from None
    settled = _settle(order, payload.razorpay_payment_id, paid)
    await db.flush()
    await referrals.mark_used(db, order_id=order.id)
    referral = await referrals.has_reward(db, user_id=user_id)
    return _plan_from(settled, datetime.now(UTC), price, referral=referral)


# The events that mean an order was paid. Others are acknowledged and ignored.
_PAID_EVENTS = ("order.paid", "payment.captured")


async def handle_webhook(db: AsyncSession, *, body: bytes, signature: str | None) -> None:
    secret = get_settings().razorpay_webhook_secret
    if not secret or razorpay.keys() is None:
        raise UnavailableError("Webhooks are not set up.")
    if not signature or not razorpay.webhook_signature_ok(
        body=body, signature=signature, secret=secret
    ):
        logger.warning("Refused a Razorpay webhook with a bad signature")
        raise BadRequestError("Invalid signature.")

    try:
        event = WebhookEvent.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        logger.warning("Signed Razorpay webhook that could not be read")
        return
    if event.event not in _PAID_EVENTS or event.payload.payment is None:
        return
    payment = event.payload.payment.entity
    if not payment.order_id:
        return

    user_id = await repository.owner_of(db, payment.order_id)
    if user_id is None:
        # Not ours (a payment link, another product on the same account).
        logger.info("Webhook for unknown order %s ignored", payment.order_id)
        return
    # The same lock order as verify_payment (user lock, then row), so the two never
    # wait on each other in a circle.
    order, paid = await _locked_order(db, user_id, payment.order_id)
    if order is None:
        return
    if order.status == "paid":
        if order.razorpay_payment_id != payment.id:
            # Two captured payments for one order: one must be refunded by hand.
            logger.error("Order %s has a second captured payment %s", order.id, payment.id)
        return
    # The webhook's own copy of the payment is not trusted: Razorpay is asked again.
    try:
        await _confirmed(order, await razorpay.fetch_payment(payment.id))
    except _NotPaid as reason:
        logger.warning("Webhook for order %s not settled: %s", order.id, reason)
        return
    _settle(order, payment.id, paid)
    await db.flush()
    await referrals.mark_used(db, order_id=order.id)
