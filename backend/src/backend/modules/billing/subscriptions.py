"""Autopay: Pro renewed every month by a Razorpay subscription (a UPI or card mandate).

How it fits the rest of billing, and why:

- `start` makes the subscription on the server, at the price on sale, on the
  Razorpay plan made for that price (`_plan_id`). Someone already on Pro starts
  when their paid time ends, so nobody pays twice. A referral reward attaches the
  referral offer, which makes the first charge ₹149.
- The browser only opens Razorpay's window and hands back a signed proof. `verify`
  checks the signature, then asks Razorpay for the subscription itself.
- Every monthly charge becomes a paid `BillingOrder` (`_record_charge`), after
  Razorpay confirms the payment is captured and its invoice belongs to this
  subscription. Pro, the payments list, refunds and credits all read those rows,
  so nothing else has to know about autopay. Each charge is recorded once (its
  payment id is unique), whichever of the checkout and the webhook comes first.
- The subscription's state is only ever copied from Razorpay (`_apply`).
- Cancelling stops future charges; the month already paid for keeps running.
"""

import contextlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
)
from backend.modules.billing import funnel, prices, razorpay, repository
from backend.modules.billing import subscriptions_repository as subs_repo
from backend.modules.billing.models import BillingOrder, BillingSubscription
from backend.modules.billing.plans import PRO_MONTH, REFERRAL_AMOUNT
from backend.modules.referrals import service as referrals

logger = logging.getLogger(__name__)

# Razorpay needs a number of charges; ten years of months is "until cancelled".
TOTAL_CHARGES = 120
MAX_STARTS_PER_HOUR = 5
# A mandate made but never approved is reused for a day, then replaced.
REUSE_UNAPPROVED_FOR = timedelta(days=1)
# Pro runs a day past each paid month, so a renewal charged a little late never
# leaves a gap.
RENEWAL_GRACE = timedelta(days=1)
_STARTED = ("authenticated", "active", "pending", "paused")


class SubscriptionCheckout(BaseModel):
    """Everything Razorpay's window needs to set up the mandate. The key id is public."""

    subscription_id: str
    key_id: str
    name: str
    description: str
    email: str
    first_amount: int = Field(description="What the first charge will be, in paise.")
    amount: int = Field(description="What each later month costs, in paise.")
    currency: str
    starts_at: datetime | None = Field(description="Set when the first charge is later.")


class SubscriptionVerify(BaseModel):
    razorpay_subscription_id: str = Field(pattern=r"^sub_[A-Za-z0-9]{1,40}$")
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]{1,40}$")
    razorpay_signature: str = Field(pattern=r"^[a-f0-9]{64}$")


def _when(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC) if isinstance(value, int) and value > 0 else None


def _apply(row: BillingSubscription, entity: dict[str, Any]) -> None:
    """Copies Razorpay's view of the subscription onto ours."""
    status = entity.get("status")
    if isinstance(status, str):
        row.status = status[:16]
    row.current_start = _when(entity.get("current_start")) or row.current_start
    row.current_end = _when(entity.get("current_end")) or row.current_end
    row.charge_at = _when(entity.get("charge_at"))
    row.start_at = _when(entity.get("start_at")) or row.start_at
    row.ended_at = _when(entity.get("ended_at")) or row.ended_at


async def _plan_id(db: AsyncSession, amount: int, currency: str, description: str) -> str:
    if found := await subs_repo.plan_id_for(db, amount, currency):
        return found
    made = await razorpay.create_plan(
        amount=amount, currency=currency, name="Rolesetu Pro", description=description
    )
    plan_id = made.get("id")
    if not isinstance(plan_id, str) or not plan_id.startswith("plan_"):
        raise UnavailableError("Payments are not available right now. Nothing was charged.")
    return await subs_repo.save_plan(db, plan_id, amount, currency)


async def start(
    db: AsyncSession, *, user_id: uuid.UUID, email: str, attempt_id: uuid.UUID | None
) -> SubscriptionCheckout:
    found_keys = razorpay.require_keys()
    price, on_sale = await prices.current_price(db, PRO_MONTH.plan)
    if not on_sale:
        raise UnavailableError("Pro is not on sale right now. Nothing was charged.")
    now = datetime.now(UTC)

    await repository.lock_user(db, user_id)
    if await subs_repo.started_since(db, user_id, now - timedelta(hours=1)) >= MAX_STARTS_PER_HOUR:
        raise RateLimitedError(
            "You have started autopay a lot in the last hour. Please wait a little."
        )

    existing = await subs_repo.latest_live(db, user_id)
    if existing is not None and existing.status in _STARTED and not existing.cancel_at_cycle_end:
        raise ConflictError("Autopay is already on. You can manage it on your Plan page.")
    # A mandate set to stop at the end of its month runs out on its own; the new one
    # starts when the paid time ends (below). Only one never approved is replaced.
    if existing is not None and existing.status == "created":
        if existing.amount == price.amount and now - existing.created_at < REUSE_UNAPPROVED_FOR:
            return _checkout(existing, found_keys.key_id, email, price.description)
        _apply(
            existing,
            await razorpay.cancel_subscription(
                existing.razorpay_subscription_id, at_cycle_end=False
            ),
        )

    plan_id = await _plan_id(db, price.amount, price.currency, price.description)
    _, until = await repository.order_checks(db, user_id, now)
    starts = until if until and until > now + timedelta(hours=1) else None

    offer_id = get_settings().razorpay_referral_offer_id
    reward = (
        await referrals.find_reward(db, user_id=user_id)
        if offer_id and price.currency == "INR"
        else None
    )
    try:
        made = await razorpay.create_subscription(
            plan_id=plan_id,
            total_count=TOTAL_CHARGES,
            notes={"user_id": str(user_id), "plan": price.plan},
            start_at=int(starts.timestamp()) if starts else None,
            offer_id=offer_id if reward else None,
        )
    except UnavailableError:
        await funnel.record_failure(
            user_id=user_id,
            step="start_failed",
            attempt_id=attempt_id,
            detail={"reason": "razorpay_unavailable", "kind": "autopay"},
        )
        raise
    subscription_id = made.get("id")
    if not isinstance(subscription_id, str) or not subscription_id.startswith("sub_"):
        logger.error("Razorpay made a subscription that does not look like one")
        raise UnavailableError("Payments are not available right now. Nothing was charged.")

    row = BillingSubscription(
        id=uuid.uuid4(),
        user_id=user_id,
        razorpay_subscription_id=subscription_id,
        razorpay_plan_id=plan_id,
        amount=price.amount,
        currency=price.currency,
        days=price.days,
        status="created",
        offer_id=offer_id if reward else None,
        referral_id=reward.id if reward else None,
    )
    _apply(row, made)
    db.add(row)
    await db.flush()
    funnel.record(
        db,
        user_id=user_id,
        step="autopay_created",
        source="server",
        attempt_id=attempt_id,
        detail={
            "subscription": subscription_id,
            "referral": reward is not None,
            "starts_later": starts is not None,
        },
    )
    return _checkout(row, found_keys.key_id, email, price.description)


def _checkout(
    row: BillingSubscription, key_id: str, email: str, description: str
) -> SubscriptionCheckout:
    first = min(row.amount, REFERRAL_AMOUNT) if row.referral_id else row.amount
    return SubscriptionCheckout(
        subscription_id=row.razorpay_subscription_id,
        key_id=key_id,
        name="Rolesetu",
        description=f"{description}, renews monthly",
        email=email,
        first_amount=first,
        amount=row.amount,
        currency=row.currency,
        starts_at=row.start_at if row.start_at and row.start_at > datetime.now(UTC) else None,
    )


class _NotACharge(Exception):
    """The payment did not pay for this subscription."""


async def _record_charge(db: AsyncSession, row: BillingSubscription, payment_id: str) -> bool:
    """Turns one confirmed monthly charge into a paid month of Pro. True if it was
    new. The caller holds the user's billing lock and the subscription's row lock."""
    if await subs_repo.order_for_payment(db, payment_id) is not None:
        return False  # the checkout and the webhook both got here; once is enough
    payment = await razorpay.fetch_payment(payment_id)
    if payment.get("status") == "authorized":
        payment = await razorpay.capture_payment(
            payment_id, amount=int(payment.get("amount") or 0), currency=row.currency
        )
    amount = payment.get("amount")
    invoice_id = payment.get("invoice_id")
    if (
        payment.get("status") != "captured"
        or payment.get("currency") != row.currency
        or not isinstance(amount, int)
        or not 0 < amount <= row.amount
        or not isinstance(invoice_id, str)
    ):
        raise _NotACharge(f"payment {payment_id} is not a captured charge")
    invoice = await razorpay.fetch_invoice(invoice_id)
    if invoice.get("subscription_id") != row.razorpay_subscription_id:
        raise _NotACharge(f"payment {payment_id} is for another subscription")

    now = datetime.now(UTC)
    starts = row.current_start or now
    ends = max(row.current_end or starts, starts + timedelta(days=row.days)) + RENEWAL_GRACE
    first_charge = await subs_repo.charges_of(db, row.user_id, row.created_at) == 0
    order = BillingOrder(
        id=uuid.uuid4(),
        user_id=row.user_id,
        razorpay_order_id=str(payment.get("order_id") or f"autopay_{payment_id}")[:64],
        razorpay_payment_id=payment_id,
        plan=PRO_MONTH.plan,
        amount=amount,
        currency=row.currency,
        status="paid",
        days=row.days,
        paid_at=now,
        pro_starts_at=starts,
        pro_ends_at=ends,
    )
    await repository.add(db, order)
    if first_charge and row.referral_id:
        await referrals.spend(db, referral_id=row.referral_id, order_id=order.id)
    funnel.record(
        db,
        user_id=row.user_id,
        step="charge_recorded",
        source="server",
        detail={"amount": amount, "payment": payment_id, "first": first_charge},
    )
    logger.info("Autopay charge %s recorded; Pro until %s", payment_id, ends.isoformat())
    return True


async def verify(db: AsyncSession, *, user_id: uuid.UUID, payload: SubscriptionVerify) -> None:
    """The checkout's word that the mandate was approved, checked with Razorpay."""
    found_keys = razorpay.require_keys()
    if not razorpay.subscription_signature_ok(
        payment_id=payload.razorpay_payment_id,
        subscription_id=payload.razorpay_subscription_id,
        signature=payload.razorpay_signature,
        secret=found_keys.key_secret,
    ):
        logger.warning("Autopay signature did not match for user %s", user_id)
        await funnel.record_failure(
            user_id=user_id,
            step="verify_failed",
            detail={"reason": "bad_signature", "kind": "autopay"},
        )
        raise BadRequestError(
            "We could not confirm your autopay. If money left your account, Pro turns on by"
            " itself within a few minutes; otherwise please try again."
        )
    await repository.lock_user(db, user_id)
    row = await subs_repo.get_owned_for_update(db, user_id, payload.razorpay_subscription_id)
    if row is None:
        raise NotFoundError("That autopay was not found. Please start the upgrade again.")
    _apply(row, await razorpay.fetch_subscription(row.razorpay_subscription_id))
    if row.status not in _STARTED:
        await funnel.record_failure(
            user_id=user_id,
            step="verify_failed",
            detail={"reason": f"status_{row.status}", "kind": "autopay"},
        )
        raise BadRequestError(
            "Razorpay has not confirmed your autopay yet. If you approved it, Pro turns on by"
            " itself within a few minutes."
        )
    if row.status == "active":
        # The approval may not itself be a charge (a later start, or a card check):
        # then the first real charge arrives by webhook.
        with contextlib.suppress(_NotACharge):
            await _record_charge(db, row, payload.razorpay_payment_id)
    funnel.record(
        db, user_id=user_id, step="autopay_verified", source="server", detail={"status": row.status}
    )


async def handle_event(
    db: AsyncSession, *, event: str, subscription_id: str, payment_id: str | None
) -> None:
    """A signed `subscription.*` webhook. Its own copy of the state is not trusted:
    Razorpay is asked again."""
    user_id = await subs_repo.owner_of(db, subscription_id)
    if user_id is None:
        logger.info("Webhook for unknown subscription %s ignored", subscription_id)
        return
    await repository.lock_user(db, user_id)
    row = await subs_repo.get_owned_for_update(db, user_id, subscription_id)
    if row is None:
        return
    _apply(row, await razorpay.fetch_subscription(subscription_id))
    if payment_id and event in ("subscription.charged", "subscription.activated"):
        try:
            await _record_charge(db, row, payment_id)
        except _NotACharge as reason:
            logger.warning("Webhook charge not recorded: %s", reason)
    funnel.record(
        db,
        user_id=user_id,
        step=f"autopay_{event.split('.', 1)[-1]}"[:32],
        source="webhook",
        detail={"status": row.status, "subscription": subscription_id},
    )


async def cancel(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Turns autopay off. A month already paid for keeps running to its end."""
    razorpay.require_keys()
    await repository.lock_user(db, user_id)
    row = await subs_repo.latest_live(db, user_id)
    if row is None:
        raise NotFoundError("Autopay is not on.")
    started = row.status in ("active", "pending")
    _apply(
        row, await razorpay.cancel_subscription(row.razorpay_subscription_id, at_cycle_end=started)
    )
    row.cancel_at_cycle_end = started
    funnel.record(
        db,
        user_id=user_id,
        step="autopay_cancel_asked",
        source="server",
        detail={"status": row.status},
    )


async def stop_all(db: AsyncSession, *, user_id: uuid.UUID, reason: str) -> None:
    """Stops every mandate the user has, at once: their Pro was taken away, refunded,
    or their account is being deleted. Raises if Razorpay cannot be reached, so the
    caller does not go on while charges could continue."""
    if razorpay.keys() is None:
        return
    for row in await subs_repo.all_live(db, user_id):
        entity = await razorpay.cancel_subscription(
            row.razorpay_subscription_id, at_cycle_end=False
        )
        _apply(row, entity)
        if row.status not in ("cancelled", "completed", "expired"):
            raise UnavailableError(
                "Could not stop this person's autopay in Razorpay. Cancel it in the Razorpay"
                " Dashboard, then try again."
            )
        funnel.record(
            db, user_id=user_id, step="autopay_stopped", source="server", detail={"reason": reason}
        )


async def is_on(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    row = await subs_repo.latest(db, user_id)
    return row is not None and row.status in _STARTED and not row.cancel_at_cycle_end
