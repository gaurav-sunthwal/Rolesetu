import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from backend.modules.profiles.schemas import ProfileRead


class AccountDeleted(BaseModel):
    # False when the data is gone but the Firebase sign-in still has to be removed by hand.
    sign_in_removed: bool
    note: str | None = None


class AdminRead(BaseModel):
    email: str


class DayCount(BaseModel):
    day: date
    signups: int
    job_checks: int


class DailyActivity(BaseModel):
    day: date
    signups: int
    job_checks: int
    applications: int


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
    # When an admin last emailed this person from the panel.
    last_emailed_at: datetime | None
    last_check_at: datetime | None


class AdminJobCheck(BaseModel):
    id: uuid.UUID
    role: str | None
    company: str | None
    url: str | None
    status: str
    score: int | None
    created_at: datetime


class AdminJobCheckRow(BaseModel):
    """A job check in the list of everyone's checks."""

    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID
    user_email: str
    role: str | None
    company: str | None
    url: str | None
    status: str
    score: int | None
    error: str | None
    # True when the page had to be read through the paid reader.
    paid_read: bool


class AdminApplicationRow(BaseModel):
    """A tracked application in the list of everyone's applications."""

    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID
    user_email: str
    role: str
    company: str
    status: str
    match_score: int | None
    applied_at: datetime | None


class AdminPreviewRow(BaseModel):
    """A job link a visitor pasted on the landing page. Belongs to no user."""

    id: uuid.UUID
    created_at: datetime
    host: str | None
    title: str | None
    company: str | None
    read: bool
    # "direct", "rendered" (the paid reader) or None when it was never fetched.
    reader: str | None


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
    """About the file. The PDF itself is opened separately."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    size_bytes: int
    status: str
    created_at: datetime


class AdminUserDetail(BaseModel):
    """What support needs to help someone. Deliberately without anything read
    from the user's Gmail (Google's rules do not allow people to read it). The
    resume file is fetched on its own, only when an admin chooses to open it.
    """

    user: AdminUserRow
    profile: ProfileRead | None
    job_checks: list[AdminJobCheck]
    applications: list[AdminApplication]
    resumes: list[AdminResume]
    gmail_last_synced_at: datetime | None
    # Emails admins sent this person from the panel (never anything from their Gmail).
    panel_emails: list["OutreachRead"]


class WaitlistRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
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


class AiCallSummary(BaseModel):
    total: int
    failed: int
    # Calls paid for by the user's own Gemini key rather than Rolesetu's.
    own_key: int
    input_tokens: int
    output_tokens: int
    # How many calls each source made in the period, whatever the filter.
    by_source: dict[str, int]


class AiCallRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID | None
    user_email: str | None
    source: str
    purpose: str
    model: str | None
    own_key: bool
    ok: bool
    error: str | None
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int


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


class OutreachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_email: str
    kind: str
    subject: str
    status: str
    error: str | None
    created_at: datetime


EmailKind = Literal["extension_nudge", "founder_note"]


class EmailCompose(BaseModel):
    """What the admin wrote. {first_name} is replaced for each person.

    `kind` says what is added after the message: the extension's store link
    and how to connect it (extension_nudge), or only the sign-off (founder_note).
    """

    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    kind: EmailKind = "extension_nudge"


class EmailTemplate(BaseModel):
    """A ready-made email for one person, already filled in with what they have done."""

    id: str
    label: str
    hint: str
    kind: EmailKind
    subject: str
    message: str
    recommended: bool


class EmailDefaults(BaseModel):
    subject: str
    message: str
    placeholder: str
    # People a bulk send would reach now, and the most one send will email.
    recipients: int
    max_per_send: int
    # False when no email provider is set up, so nothing can be sent.
    configured: bool


class BulkQueued(BaseModel):
    queued: int


# The user detail names OutreachRead before it is defined above.
AdminUserDetail.model_rebuild()
