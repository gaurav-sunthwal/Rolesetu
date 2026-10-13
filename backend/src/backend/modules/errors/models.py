from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class ErrorEvent(IdMixin, TimestampMixin, Base):
    """One thing that went wrong, kept so it can be seen in the admin panel.

    Not tied to a user: an error stays readable after an account is deleted,
    and nothing about the person who hit it is stored.
    """

    __tablename__ = "error_events"
    __table_args__ = (
        Index("ix_error_events_created", "created_at"),
        Index("ix_error_events_fingerprint_created", "fingerprint", "created_at"),
    )

    # Where it happened: "api" (a request), "job-check" (scoring in the
    # background) or "job-link" (a job page that could not be read).
    source: Mapped[str]
    # "error" for a fault of ours, "warning" for a failure we handled.
    level: Mapped[str] = mapped_column(default="error")
    # The same for every occurrence of one problem, so they can be counted together.
    fingerprint: Mapped[str]
    # The route as written in the code ("/api/v1/matches/{match_id}"), not the address used.
    route: Mapped[str | None] = mapped_column(default=None)
    method: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[int | None] = mapped_column(default=None)
    # The kind of error, e.g. "KeyError" or "LLMUnavailableError".
    code: Mapped[str | None] = mapped_column(default=None)
    message: Mapped[str] = mapped_column(Text)
    stack: Mapped[str | None] = mapped_column(Text, default=None)
