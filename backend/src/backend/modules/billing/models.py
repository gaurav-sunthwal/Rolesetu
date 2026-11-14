import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class BillingOrder(IdMixin, TimestampMixin, Base):
    """One attempt to buy a plan: made as "created" with the Razorpay order, and
    turned "paid" only after Razorpay itself confirms the payment.

    A paid row is what makes someone Pro: they are Pro while now falls inside one
    of their paid rows' [pro_starts_at, pro_ends_at). Nothing else stores the plan,
    so it cannot drift from what was paid for.
    """

    __tablename__ = "billing_orders"
    __table_args__ = (
        Index("ix_billing_orders_user_created", "user_id", "created_at"),
        Index("ix_billing_orders_status_created", "status", "created_at"),
        Index(
            "ix_billing_orders_user_paid_ends",
            "user_id",
            "pro_ends_at",
            postgresql_where=text("status = 'paid'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    razorpay_order_id: Mapped[str] = mapped_column(String(64), unique=True)
    # Unique: one payment can never pay for two orders.
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    plan: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), default="created")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    pro_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    pro_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Days of Pro this order buys, fixed when the order is made (prices can change).
    days: Mapped[int | None] = mapped_column(default=None)
    # Set when an admin refunded it through Razorpay (status "refunded").
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    refund_id: Mapped[str | None] = mapped_column(String(64), default=None)
    # Why an admin granted, refunded or removed it.
    note: Mapped[str | None] = mapped_column(String(200), default=None)


class BillingPlan(TimestampMixin, Base):
    """What a plan costs now. Edited from the admin panel; a new price applies to
    orders made after it, never to ones already paid."""

    __tablename__ = "billing_plans"

    plan: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(String(120))
    # In the currency's smallest unit (paise for INR).
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    days: Mapped[int]
    # Off: the plan cannot be bought (existing Pro is untouched).
    active: Mapped[bool] = mapped_column(default=True)
    updated_by: Mapped[str | None] = mapped_column(String(320), default=None)


class BillingAdminAction(IdMixin, TimestampMixin, Base):
    """Every change an admin made to someone's plan or to a price: who, what, why."""

    __tablename__ = "billing_admin_actions"
    __table_args__ = (
        Index("ix_billing_admin_actions_created", "created_at"),
        Index("ix_billing_admin_actions_user", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_orders.id", ondelete="SET NULL"), default=None
    )
    # "grant", "refund", "revoke", "end_pro" or "price".
    action: Mapped[str] = mapped_column(String(20))
    admin_email: Mapped[str] = mapped_column(String(320))
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    amount: Mapped[int | None] = mapped_column(default=None)
    days: Mapped[int | None] = mapped_column(default=None)


class RazorpayPlan(TimestampMixin, Base):
    """The Razorpay plan made for one price. A Razorpay plan's amount can never
    change, so each price Rolesetu charges gets its own, made the first time it is
    needed and reused after."""

    __tablename__ = "billing_razorpay_plans"
    __table_args__ = (UniqueConstraint("amount", "currency", name="uq_razorpay_plan_price"),)

    razorpay_plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))


# Razorpay states in which a subscription can still charge.
LIVE_SUBSCRIPTION_STATES = ("created", "authenticated", "active", "pending", "paused")


class BillingSubscription(IdMixin, TimestampMixin, Base):
    """One autopay mandate. Its state is copied from Razorpay (never trusted from a
    browser); each monthly charge becomes a paid BillingOrder, which is what makes
    the user Pro."""

    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        Index("ix_billing_subscriptions_user_created", "user_id", "created_at"),
        Index("ix_billing_subscriptions_status_updated", "status", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    razorpay_subscription_id: Mapped[str] = mapped_column(String(64), unique=True)
    razorpay_plan_id: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    days: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="created")
    offer_id: Mapped[str | None] = mapped_column(String(32), default=None)
    # The referral reward the first charge's discount spends.
    referral_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("referrals.id", ondelete="SET NULL"), default=None
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    current_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    current_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancel_at_cycle_end: Mapped[bool] = mapped_column(default=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class BillingFunnelEvent(IdMixin, TimestampMixin, Base):
    """One step someone took (or one thing that went wrong) on the way to paying:
    the page seen, the window opened or closed, a failure with Razorpay's reason,
    a charge. Read by the admin Payment funnel and the reminder emails."""

    __tablename__ = "billing_funnel_events"
    __table_args__ = (
        Index("ix_billing_funnel_created", "created_at"),
        Index("ix_billing_funnel_user_created", "user_id", "created_at"),
        Index("ix_billing_funnel_step_created", "step", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # One upgrade attempt, from the click to its end, shares this id.
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    step: Mapped[str] = mapped_column(String(32))
    # "client" (the dashboard said so), "server" or "webhook".
    source: Mapped[str] = mapped_column(String(8))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
