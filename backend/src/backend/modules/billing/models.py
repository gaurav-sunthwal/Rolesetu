import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
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
