from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class WaitlistEntry(IdMixin, TimestampMixin, Base):
    """Someone who asked to be emailed when the browser extension is released.

    Not tied to an account: most people join from the landing page before they
    have one.
    """

    __tablename__ = "extension_waitlist"
    __table_args__ = (Index("ix_extension_waitlist_client_created", "client_hash", "created_at"),)

    # Stored in lower case, so one address cannot join twice.
    email: Mapped[str] = mapped_column(unique=True, index=True)
    # sha256 of the visitor's IP address, kept only to limit sign-ups from one place.
    client_hash: Mapped[str]
