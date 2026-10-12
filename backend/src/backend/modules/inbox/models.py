import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class Integration(IdMixin, TimestampMixin, Base):
    """A mailbox the user has connected. The refresh token is encrypted at rest
    and is the only credential kept; access tokens live for one sync.
    """

    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_integrations_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(default="gmail")
    account_email: Mapped[str]
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(Text)
    # idle | syncing
    sync_status: Mapped[str] = mapped_column(default="idle")
    sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # What went wrong last time, in words the user can act on.
    last_error: Mapped[str | None] = mapped_column(Text, default=None)


class EmailMessage(IdMixin, TimestampMixin, Base):
    """A job-related mail. Only who sent it, its subject, when, and what it was
    judged to be are kept. The body is never stored.
    """

    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("user_id", "gmail_message_id", name="uq_email_messages_user_gmail_id"),
        Index("ix_email_messages_user_received", "user_id", "received_at", "id"),
        Index("ix_email_messages_user_state", "user_id", "state"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    gmail_message_id: Mapped[str]
    sender_name: Mapped[str]
    sender_email: Mapped[str]
    subject: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # applied | rejected | interview | assessment | offer | unclear
    kind: Mapped[str]
    company: Mapped[str | None] = mapped_column(default=None)
    role: Mapped[str | None] = mapped_column(default=None)
    # linked: updated an application already tracked. created: made a new one.
    # review: we were not sure, the user decides. dismissed: the user said no.
    state: Mapped[str]
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), default=None
    )


class Interview(IdMixin, TimestampMixin, Base):
    """A scheduled interview: when, where, and for which application. Found in
    an interview mail, and editable by the user because mails are not always clear.
    """

    __tablename__ = "interviews"
    __table_args__ = (Index("ix_interviews_user_starts", "user_id", "starts_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), default=None
    )
    # The mail it came from. Null once that record is gone.
    email_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="SET NULL"), default=None
    )
    company: Mapped[str | None] = mapped_column(default=None)
    role: Mapped[str | None] = mapped_column(default=None)
    # Null until a time is known. When only the day is known, `has_time` is
    # False and this holds midnight UTC of that day.
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    has_time: Mapped[bool] = mapped_column(default=False)
    # A meeting link (Meet, Zoom, Teams) or a link for choosing a slot.
    link: Mapped[str | None] = mapped_column(Text, default=None)
    location: Mapped[str | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    # True once the user has set the time themselves; later mails then leave it alone.
    edited: Mapped[bool] = mapped_column(default=False)
