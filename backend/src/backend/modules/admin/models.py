import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class AdminAction(IdMixin, TimestampMixin, Base):
    """One thing an admin did in the admin panel: looked at a user's data, or
    deleted an account. Written so there is always a record of who saw what.
    """

    __tablename__ = "admin_actions"
    __table_args__ = (Index("ix_admin_actions_created", "created_at", "id"),)

    admin_email: Mapped[str]
    # "user.view" | "user.delete" | "waitlist.view" | "errors.clear" | "email.send" | "email.bulk"
    action: Mapped[str]
    target_type: Mapped[str]
    target_id: Mapped[str]
    summary: Mapped[str | None] = mapped_column(Text, default=None)


class OutreachEmail(IdMixin, TimestampMixin, Base):
    """An email an admin sent to a user from the admin panel.

    Kept so the panel can say who was already written to, and so a bulk send
    never writes to the same person twice in a short time.
    """

    __tablename__ = "outreach_emails"
    __table_args__ = (Index("ix_outreach_emails_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    admin_email: Mapped[str]
    # Which kind of email: "extension_nudge" for now.
    kind: Mapped[str]
    subject: Mapped[str]
    # "sent", or "failed" with the reason in `error`.
    status: Mapped[str]
    error: Mapped[str | None] = mapped_column(Text, default=None)
