from typing import Any

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class JobPreview(IdMixin, TimestampMixin, Base):
    """One attempt to read a job link for a visitor who is not signed in.

    Belongs to no user. A row is kept for a day and does three jobs: the job it
    read is reused for anyone pasting the same link, the rows per visitor are
    the rate limit, and the rows read through the paid reader are its budget.
    """

    __tablename__ = "job_previews"
    __table_args__ = (
        Index("ix_job_previews_url_created", "url_hash", "created_at"),
        Index("ix_job_previews_client_created", "client_hash", "created_at"),
        Index("ix_job_previews_created", "created_at"),
    )

    url_hash: Mapped[str]
    # The site the link is on (e.g. "naukri.com"), so we can see which sites fail.
    # None on rows written before this was recorded.
    host: Mapped[str | None] = mapped_column(default=None)
    # sha256 of the visitor's IP address; the address itself is never stored.
    client_hash: Mapped[str]
    # "direct" or "rendered" (the paid reader was called). None if the link was never fetched.
    reader: Mapped[str | None] = mapped_column(default=None)
    # The job that was read, or None when the link could not be read.
    page: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
