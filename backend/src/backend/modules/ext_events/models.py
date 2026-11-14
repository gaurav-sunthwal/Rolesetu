"""Extension usage events: one row per thing a user did with the extension.

Stored for 90 days then purged. Never holds page content, job text, what the user
typed, or a full URL: only the user, the site's hostname, the event's name, a small
number and a few short labels (`props`). The full list of names is `EventName` in
`schemas.py`.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class ExtEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "ext_events"
    __table_args__ = (
        # Fast per-user event feed.
        Index("ix_ext_events_user_created", "user_id", "created_at", "id"),
        # Admin aggregation by event type over time.
        Index("ix_ext_events_name_created", "name", "created_at"),
        # Admin aggregation by site.
        Index("ix_ext_events_host_created", "host", "created_at"),
        # One row per event, however often the extension retries a batch.
        Index(
            "uq_ext_events_client_id",
            "client_id",
            unique=True,
            postgresql_where=text("client_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(40))
    # The hostname of the page (e.g. "capgemini.com"). Never the full URL.
    host: Mapped[str | None] = mapped_column(String(120), default=None)
    # A small number that gives the event meaning: fields filled, score, etc.
    count: Mapped[int | None] = mapped_column(default=None)
    # The id the extension gave the event, so a retried batch is stored once.
    client_id: Mapped[str | None] = mapped_column(String(36), default=None)
    # The extension's version, to tell which release a problem started in.
    version: Mapped[str | None] = mapped_column(String(20), default=None)
    # One browser session of the extension, to follow one visit through a form.
    session_id: Mapped[str | None] = mapped_column(String(36), default=None)
    # A few short labels ({"source": "pitch", "mode": "write"}). Never user text.
    props: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
