import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

ApplicationStatus = Literal["saved", "applied", "replied", "interview", "offer", "rejected"]
# Who recorded a change: the user in the dashboard, or the browser extension on a job page.
EventSource = Literal["manual", "extension"]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Url = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]


class ApplicationCreate(BaseModel):
    role: Name
    company: Name
    url: Url | None = None
    location: Location | None = None
    status: ApplicationStatus = "saved"
    applied_at: datetime | None = None
    contact_email: EmailStr | None = None
    notes: Notes | None = None
    # When tracking from a match, the server copies the job and score itself.
    match_id: uuid.UUID | None = None
    # Left out by the dashboard, which means "manual".
    source: EventSource | None = None


class ApplicationUpdate(BaseModel):
    role: Name | None = None
    company: Name | None = None
    url: Url | None = None
    location: Location | None = None
    status: ApplicationStatus | None = None
    applied_at: datetime | None = None
    contact_email: EmailStr | None = None
    notes: Notes | None = None
    # Left out by the dashboard, which means "manual".
    source: EventSource | None = None


class ApplicationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    source: str
    occurred_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    company: str
    url: str | None
    location: str | None
    status: ApplicationStatus
    applied_at: datetime | None
    contact_email: str | None
    notes: str | None
    match_score: int | None
    job_id: uuid.UUID | None
    needs_follow_up: bool = False
    # Opens the newest mail about this application in the user's Gmail, when
    # there is one. Filled in for lists.
    gmail_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(ApplicationRead):
    events: list[ApplicationEventRead]


class ApplicationStats(BaseModel):
    total: int
    sent: int
    responded: int
    # None until at least one application has been sent.
    reply_rate: float | None = Field(ge=0, le=1)
    interviews: int
    offers: int
    rejections: int
    follow_ups_due: int
    by_status: dict[ApplicationStatus, int]
