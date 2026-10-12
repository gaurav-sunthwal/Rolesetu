import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, IdMixin, TimestampMixin


class Job(IdMixin, TimestampMixin, Base):
    """A job description a user checked. Scoped to the user who pasted it."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_user_hash", "user_id", "content_hash"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    url: Mapped[str | None] = mapped_column(Text, default=None)
    role: Mapped[str | None] = mapped_column(default=None)
    company: Mapped[str | None] = mapped_column(default=None)
    jd_text: Mapped[str] = mapped_column(Text)
    # sha256 of the normalised description: the cache key for repeat checks.
    content_hash: Mapped[str]
    job_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)


class Match(IdMixin, TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_user_created", "user_id", "created_at", "id"),
        Index("ix_matches_job_version", "job_id", "profile_version"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    profile_version: Mapped[int]
    # pending | completed | failed
    status: Mapped[str] = mapped_column(default="pending")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    score: Mapped[int | None] = mapped_column(default=None)
    # The score from skills alone, before any seniority cap.
    raw_score: Mapped[int | None] = mapped_column(default=None)
    seniority_note: Mapped[str | None] = mapped_column(Text, default=None)
    # The experience the job asks for against the candidate's. None on results
    # scored before this was recorded.
    experience: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    skill_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    prompt_versions: Mapped[str | None] = mapped_column(default=None)

    job: Mapped[Job] = relationship(lazy="raise")
