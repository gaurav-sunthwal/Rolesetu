import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class MatchShare(IdMixin, TimestampMixin, Base):
    """A match score its owner chose to make public behind a short link.

    It holds a copy of only what the public card shows (job, score, skill
    names), taken when the owner shares. Nothing from the resume is copied, and
    later changes to the match do not leak out through an old link.
    """

    __tablename__ = "match_shares"
    __table_args__ = (
        Index("ix_match_shares_user_created", "user_id", "created_at"),
        Index("ix_match_shares_match", "match_id", unique=True),
    )

    slug: Mapped[str] = mapped_column(String(16), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE")
    )
    role: Mapped[str | None] = mapped_column(String(160), default=None)
    company: Mapped[str | None] = mapped_column(String(160), default=None)
    score: Mapped[int]
    matched: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Empty unless the owner chose to show what they are missing.
    gaps: Mapped[list[str]] = mapped_column(JSONB, default=list)
