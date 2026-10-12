import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class SavedAnswer(IdMixin, TimestampMixin, Base):
    """A reusable answer to a common application question (notice period, CTC...)."""

    __tablename__ = "saved_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_key", name="uq_saved_answers_user_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_key: Mapped[str]
    answer: Mapped[str] = mapped_column(Text)
