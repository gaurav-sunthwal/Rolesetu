import uuid
from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class Profile(IdMixin, TimestampMixin, Base):
    """One row per user. The list sections are JSONB documents because they are
    always read and written together; `version` bumps on every change so cached
    match scores know when they are stale.
    """

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    full_name: Mapped[str | None] = mapped_column(default=None)
    headline: Mapped[str | None] = mapped_column(default=None)
    location: Mapped[str | None] = mapped_column(default=None)
    phone: Mapped[str | None] = mapped_column(default=None)
    links: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    skills: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    projects: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(default=1)
