import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class ResumeFile(IdMixin, TimestampMixin, Base):
    """An uploaded resume. The PDF lives in private storage under `storage_key`;
    `parsed_json` is the cleaned profile data read from it.
    """

    __tablename__ = "resume_files"
    __table_args__ = (Index("ix_resume_files_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    storage_key: Mapped[str] = mapped_column(Text)
    filename: Mapped[str]
    size_bytes: Mapped[int]
    # Always "parsed" today (reading is instant). Kept as a column so slower
    # readers, such as OCR for scans, can report progress later.
    status: Mapped[str] = mapped_column(default="parsed")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    # Which version of the local parser produced `parsed_json`.
    parser_version: Mapped[str | None] = mapped_column(default=None)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
