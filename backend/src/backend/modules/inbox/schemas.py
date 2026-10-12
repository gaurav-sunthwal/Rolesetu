import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Kind = Literal["applied", "rejected", "interview", "assessment", "offer", "unclear"]
State = Literal["linked", "created", "review", "dismissed"]


class InboxStatus(BaseModel):
    # False until the server has Google credentials.
    configured: bool
    connected: bool
    account_email: str | None
    sync_status: Literal["idle", "syncing"]
    last_synced_at: datetime | None
    last_error: str | None
    lookback_days: int
    # Mails waiting for the user to say which application they belong to.
    review_count: int


class ConnectUrl(BaseModel):
    url: str


class EmailRead(BaseModel):
    """A job-related mail. The body is never stored or returned."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    kind: Kind
    company: str | None
    role: str | None
    state: State
    application_id: uuid.UUID | None
    # Opens this mail in the user's own Gmail.
    gmail_url: str | None = None


class ReviewAction(BaseModel):
    """What to do with a mail in the Review list."""

    action: Literal["dismiss", "link"]
    application_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _link_needs_an_application(self) -> Self:
        if self.action == "link" and self.application_id is None:
            raise ValueError("Choose the application this mail belongs to.")
        return self


class Totals(BaseModel):
    applied: int
    waiting: int
    rejected: int
    interviews: int
    offers: int


class FindingRead(BaseModel):
    title: str
    detail: str


class InboxInsights(BaseModel):
    totals: Totals
    findings: list[FindingRead]


class InterviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID | None
    company: str | None
    role: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    # False when only the day is known, or nothing is.
    has_time: bool
    link: str | None
    location: str | None
    notes: str | None
    # The subject of the mail this was read from, and a link that opens it in Gmail.
    mail_subject: str | None = None
    gmail_url: str | None = None


class InterviewUpdate(BaseModel):
    """The user's corrections. Only the fields sent are changed."""

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    link: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None

    @model_validator(mode="after")
    def _times_make_sense(self) -> Self:
        for moment in (self.starts_at, self.ends_at):
            if moment is not None and moment.tzinfo is None:
                raise ValueError("Times must include a timezone.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("The end must be after the start.")
        return self
