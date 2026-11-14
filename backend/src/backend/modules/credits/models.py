import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin


class CreditUsage(TimestampMixin, Base):
    """AI credits one user spent in one calendar month (UTC). One row per user and
    month, changed only by a single guarded UPDATE, so parallel requests can never
    spend past the plan's allowance."""

    __tablename__ = "credit_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # The first day of the month the credits were spent in.
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    used: Mapped[int] = mapped_column(default=0)
