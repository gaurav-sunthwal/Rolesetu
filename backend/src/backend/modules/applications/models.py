import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, IdMixin, TimestampMixin


class Application(IdMixin, TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_applications_user_idempotency"),
        Index("ix_applications_user_created", "user_id", "created_at", "id"),
        Index("ix_applications_user_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), default=None
    )
    role: Mapped[str]
    company: Mapped[str]
    url: Mapped[str | None] = mapped_column(Text, default=None)
    location: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="saved")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    contact_email: Mapped[str | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Snapshot of the score at the time the job was tracked.
    match_score: Mapped[int | None] = mapped_column(default=None)
    idempotency_key: Mapped[str | None] = mapped_column(default=None)

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.occurred_at.desc()",
        lazy="raise",
    )


class ApplicationEvent(IdMixin, Base):
    __tablename__ = "application_events"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str]
    # manual | gmail | extension
    source: Mapped[str] = mapped_column(default="manual")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="events", lazy="raise")
