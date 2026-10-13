from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class AdminAction(IdMixin, TimestampMixin, Base):
    """One thing an admin did in the admin panel: looked at a user's data, or
    deleted an account. Written so there is always a record of who saw what.
    """

    __tablename__ = "admin_actions"
    __table_args__ = (Index("ix_admin_actions_created", "created_at", "id"),)

    admin_email: Mapped[str]
    # "user.view" | "user.delete" | "waitlist.view" | "errors.clear"
    action: Mapped[str]
    target_type: Mapped[str]
    target_id: Mapped[str]
    summary: Mapped[str | None] = mapped_column(Text, default=None)
