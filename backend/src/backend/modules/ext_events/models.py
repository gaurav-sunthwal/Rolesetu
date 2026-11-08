"""Extension usage events — one row per user action in the extension.

Stored for 90 days then purged. Never stores any page content, job text,
or personal data beyond user_id and the site hostname.
"""

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class ExtEvent(IdMixin, TimestampMixin, Base):
    """One thing a user did with the extension.

    Tracked event names:
      autofill_offered   – form found, offer banner shown (count = fillable fields)
      autofill_filled    – user clicked Fill, fields were written (count = filled)
      autofill_failed    – fill ran but form rejected all values
      autofill_learned   – user typed/picked a new answer that was saved
      job_scored         – match score returned (score = 0-100)
      panel_opened       – user opened the side panel manually
      apply_clicked      – user clicked an Apply button we detected
    """

    __tablename__ = "ext_events"
    __table_args__ = (
        # Fast per-user event feed.
        Index("ix_ext_events_user_created", "user_id", "created_at", "id"),
        # Admin aggregation by event type over time.
        Index("ix_ext_events_name_created", "name", "created_at"),
        # Admin aggregation by site.
        Index("ix_ext_events_host_created", "host", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # What happened: one of the seven names above.
    name: Mapped[str] = mapped_column(String(40))
    # The hostname of the career page (e.g. "capgemini.com"). Never the full URL.
    host: Mapped[str | None] = mapped_column(String(120), default=None)
    # A small number that gives the event meaning: fields found/filled, score, etc.
    count: Mapped[int | None] = mapped_column(default=None)
