import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class UserLlmKey(IdMixin, TimestampMixin, Base):
    """A user's own Gemini key — the last fallback after both server keys,
    stored encrypted (see core/encryption.py), never exposed back as plaintext.
    One row per (user, provider); re-saving replaces it.
    """

    __tablename__ = "user_llm_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(default="gemini")
    encrypted_key: Mapped[str]
