import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class AiCall(IdMixin, TimestampMixin, Base):
    """One request to the model, kept so the admin panel can show how much AI
    each part of Rolesetu uses. Only what the call was for and what it cost is
    stored, never the prompt or the answer.
    """

    __tablename__ = "ai_calls"
    __table_args__ = (
        Index("ix_ai_calls_created", "created_at", "id"),
        Index("ix_ai_calls_source_created", "source", "created_at"),
        Index("ix_ai_calls_user_created", "user_id", "created_at"),
    )

    # Deleting an account deletes its calls too.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
    # Where it was asked from: "extension" (a job check from the extension),
    # "dashboard" (a job check from the website), "resume" (the resume editor's
    # assistant) or "other" (scripts and evals).
    source: Mapped[str]
    # What the model was asked to do: "job-read", "skill-judge" or "resume-assistant".
    purpose: Mapped[str]
    # The model that answered, or the last one tried when none did.
    model: Mapped[str | None] = mapped_column(default=None)
    # True when the user's own Gemini key paid for it, not Rolesetu's.
    own_key: Mapped[bool] = mapped_column(default=False)
    ok: Mapped[bool] = mapped_column(default=True)
    # The kind of error behind a failed call, e.g. "ServerError" or "TimeoutError".
    error: Mapped[str | None] = mapped_column(default=None)
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    output_tokens: Mapped[int | None] = mapped_column(default=None)
    duration_ms: Mapped[int] = mapped_column(default=0)
