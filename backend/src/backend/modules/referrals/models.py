import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class ReferralCode(TimestampMixin, Base):
    """The short code in a user's invite link (rolesetu…/?ref=CODE)."""

    __tablename__ = "referral_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(12), unique=True)


class Referral(IdMixin, TimestampMixin, Base):
    """One person who joined through someone's link.

    It becomes a reward (`qualified_at`) once that person really uses Rolesetu, and is
    spent (`used_at`) by the referrer's next paid month at the referral price.
    """

    __tablename__ = "referrals"
    __table_args__ = (Index("ix_referrals_referrer_created", "referrer_id", "created_at"),)

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # Unique: a person can be invited only once, by one person.
    referred_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The order this reward is set aside for, and when that order was paid.
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_orders.id", ondelete="SET NULL"), default=None
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
