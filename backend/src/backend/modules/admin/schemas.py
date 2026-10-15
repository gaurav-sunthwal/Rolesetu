import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from backend.modules.profiles.schemas import ProfileRead


class AdminRead(BaseModel):
    email: str


class DayCount(BaseModel):
    day: date
    signups: int
    job_checks: int


class SiteReads(BaseModel):
    """Job links visitors pasted on the landing page in the last day, by site."""

    host: str
    read: int
    failed: int
    paid: int


class AdminStats(BaseModel):
    users: int
    users_with_profile: int
    job_checks: int
    applications: int
    gmail_connected: int
    # Users whose browser extension is connected to their account, and how many
    # of those it has been used by in the last seven days.
    extension_connected: int
    extension_active_week: int
    waitlist: int
    previews_today: int
    errors_today: int
    # Reads through the paid page reader in the last day, by visitors and by users.
    paid_reads_today: int
    daily: list[DayCount]
    sites: list[SiteReads]


class AdminUserRow(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    created_at: datetime
    has_profile: bool
    resumes: int
    job_checks: int
    applications: int
    gmail_connected: bool
    extension_connected: bool
    last_check_at: datetime | None


class AdminJobCheck(BaseModel):
    id: uuid.UUID
    role: str | None
    company: str | None
    url: str | None
    status: str
    score: int | None
    created_at: datetime


class AdminApplication(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    company: str
    status: str
    match_score: int | None
    applied_at: datetime | None
    created_at: datetime


class AdminResume(BaseModel):
    """About the file only. The resume itself is not served to admins."""

    model_config = ConfigDict(from_attributes=True)

    filename: str
    size_bytes: int
    status: str
    created_at: datetime


class AdminUserDetail(BaseModel):
    """What support needs to help someone. Deliberately without anything read
    from the user's Gmail (Google's rules do not allow people to read it) and
    without the resume file.
    """

    user: AdminUserRow
    profile: ProfileRead | None
    job_checks: list[AdminJobCheck]
    applications: list[AdminApplication]
    resumes: list[AdminResume]
    gmail_last_synced_at: datetime | None


class WaitlistRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class AdminActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_email: str
    action: str
    target_type: str
    target_id: str
    summary: str | None
    created_at: datetime


class ErrorGroup(BaseModel):
    """One problem: every event with the same cause, counted together."""

    fingerprint: str
    source: str
    level: str
    route: str | None
    method: str | None
    status: int | None
    code: str | None
    message: str
    events: int
    first_at: datetime
    last_at: datetime


class ErrorSummary(BaseModel):
    groups: list[ErrorGroup]
    # How many events each source produced in the period, whatever the filter.
    by_source: dict[str, int]


class ErrorEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    level: str
    route: str | None
    method: str | None
    status: int | None
    code: str | None
    message: str
    stack: str | None
    created_at: datetime
