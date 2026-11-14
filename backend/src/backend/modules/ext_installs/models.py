"""Installs of the extension, followed from the moment of install, before (and
whether or not) the person ever signs in.

An install is known only by a random id the extension made for itself. Nothing
here names a person until they connect an account (`user_id`). Stored: the
browser's own description of itself (version, OS, language, time zone), never an
address (`client_hash` is a one-way hash, used only to rate limit and to spot many
installs from one machine).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class ExtInstall(IdMixin, TimestampMixin, Base):
    __tablename__ = "ext_installs"
    __table_args__ = (
        Index("ix_ext_installs_created", "created_at"),
        Index("ix_ext_installs_client_created", "client_hash", "created_at"),
        Index("ix_ext_installs_user", "user_id"),
    )

    install_id: Mapped[str] = mapped_column(String(36), unique=True)
    # Set once the install is connected to an account; removed with the account.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
    client_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    version: Mapped[str | None] = mapped_column(String(20), default=None)
    browser: Mapped[str | None] = mapped_column(String(40), default=None)
    os: Mapped[str | None] = mapped_column(String(20), default=None)
    arch: Mapped[str | None] = mapped_column(String(20), default=None)
    language: Mapped[str | None] = mapped_column(String(20), default=None)
    timezone: Mapped[str | None] = mapped_column(String(50), default=None)
    # The browser says it is driven by automation (navigator.webdriver).
    automated: Mapped[bool | None] = mapped_column(default=None)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    uninstalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ExtInstallEvent(IdMixin, Base):
    """One step of an install's journey before it was connected (and the uninstall)."""

    __tablename__ = "ext_install_events"
    __table_args__ = (
        Index("ix_ext_install_events_install", "install_id", "created_at"),
        Index("ix_ext_install_events_name_created", "name", "created_at"),
        Index("uq_ext_install_events_client_id", "client_id", unique=True),
    )

    install_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(40))
    host: Mapped[str | None] = mapped_column(String(120), default=None)
    count: Mapped[int | None] = mapped_column(default=None)
    client_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[str | None] = mapped_column(String(20), default=None)
    props: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
