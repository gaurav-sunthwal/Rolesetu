from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

EventName = Literal[
    # Lifecycle
    "extension_installed",
    "extension_updated",
    "extension_connected",
    "extension_uninstalled",
    # Getting set up (sent before the browser is connected, by the extension and
    # by the website's setup pages)
    "setup_opened",
    "setup_page_seen",
    "signup_started",
    "sign_in_failed",
    "signed_in",
    "connect_failed",
    "uninstall_reason",
    "popup_opened",
    # The popup: whether the stats showed, and which button was pressed
    "popup_loaded",
    "popup_clicked",
    "page_checked",
    # What the extension found
    "job_detected",
    "form_detected",
    # Before connecting: the skills a job asks for, shown without an account
    "job_previewed",
    # The job panel
    "panel_opened",
    "job_scored",
    "apply_clicked",
    "application_tracked",
    # Autofill
    "autofill_offered",
    "autofill_filled",
    "autofill_failed",
    "autofill_undone",
    "autofill_learned",
    # Saved answers
    "answer_saved",
    "suggestion_shown",
    "suggestion_used",
    # AI answers
    "ai_requested",
    "ai_succeeded",
    "ai_failed",
    # Asking for a store review
    "review_asked",
    "review_answered",
    # Health
    "ext_error",
]

# A label's value: short words or a number, never something the user wrote.
PropValue = Annotated[str, StringConstraints(max_length=60)] | int | bool
_PROP_KEY = Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,24}$")]
# The random id an install of the extension made for itself (a UUID).
InstallId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
# Events buffered before the browser was connected are sent later with their own time.
_OLDEST = timedelta(days=7)


class ExtEventWrite(BaseModel):
    """One event sent from the extension."""

    name: EventName
    # Hostname only: the extension strips the path before sending.
    host: str | None = Field(None, max_length=120)
    # Meaning depends on the event: fields filled, match score, etc.
    count: int | None = Field(None, ge=0, le=100_000)
    # The extension's own id for the event, so a retried batch is stored once.
    id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{8,36}$")] | None = None
    version: Annotated[str, StringConstraints(pattern=r"^[0-9][0-9.]{0,19}$")] | None = None
    session: Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{8,36}$")] | None = None
    props: dict[_PROP_KEY, PropValue] | None = None
    # When it happened, if the extension held it back (not connected yet, offline).
    at: datetime | None = None

    @field_validator("props")
    @classmethod
    def _few_props(cls, props: dict[str, object] | None) -> dict[str, object] | None:
        if props is not None and len(props) > 6:
            raise ValueError("At most 6 properties per event")
        return props

    def happened_at(self, now: datetime) -> datetime | None:
        """Its own time if believable (not in the future, not older than a week)."""
        if self.at is None:
            return None
        at = self.at if self.at.tzinfo else self.at.replace(tzinfo=UTC)
        return at if now - _OLDEST <= at <= now else None


class ExtEventsWrite(BaseModel):
    """A batch: up to 50 events in one request (more after a long time offline)."""

    events: list[ExtEventWrite] = Field(..., min_length=1, max_length=50)
    # The install these came from, so its journey before connecting joins this account.
    install: InstallId | None = None


# ── Admin read schemas ────────────────────────────────────────────────────────


class ExtEventTotals(BaseModel):
    """Aggregate counts for the admin overview card."""

    autofill_offered: int = 0
    autofill_filled: int = 0
    autofill_failed: int = 0
    autofill_learned: int = 0
    job_scored: int = 0
    panel_opened: int = 0
    apply_clicked: int = 0
    # Derived: fill rate = filled / offered  (shown as 0–100 %)
    fill_rate_pct: int = 0


class ExtEventDay(BaseModel):
    """Per-day breakdown for the chart."""

    day: str  # YYYY-MM-DD
    autofill_offered: int = 0
    autofill_filled: int = 0
    job_scored: int = 0
    apply_clicked: int = 0


class ExtEventSiteRow(BaseModel):
    """Top sites, by how many autofills were offered."""

    host: str
    offered: int
    filled: int
    fill_rate_pct: int


class ExtEventStats(BaseModel):
    """Full payload returned by GET /admin/ext-events."""

    hours: int
    totals: ExtEventTotals
    daily: list[ExtEventDay]
    top_sites: list[ExtEventSiteRow]


# ── Admin: the extension analytics page ───────────────────────────────────────


class ExtOverview(BaseModel):
    # People who used the extension at all (any event), over the last day/week/month.
    active_1d: int
    active_7d: int
    active_30d: int
    # In the chosen period:
    events: int
    installs: int
    updates: int
    connects: int
    errors: int


class ExtVersionRow(BaseModel):
    version: str
    users: int


class ExtDayRow(BaseModel):
    day: str  # YYYY-MM-DD
    active_users: int
    autofill_filled: int
    answers_saved: int
    suggestions_used: int
    ai_answers: int
    jobs_scored: int


class ExtFunnelStep(BaseModel):
    """People (and times) who got this far in the period."""

    step: str
    label: str
    users: int
    events: int


class ExtFeatureRow(BaseModel):
    name: str
    events: int
    users: int


class ExtCountRow(BaseModel):
    label: str
    events: int


class ExtPopupStats(BaseModel):
    """The toolbar popup: how often it is opened, whether its stats show, and what is pressed."""

    opened: int
    opened_users: int
    # By `state`: stats (signed in, stats shown), no_stats (they failed), signed_out.
    loads: list[ExtCountRow]
    # Milliseconds the stats took to show, median, when they did.
    median_load_ms: int | None
    # By `target`: check_page, tracker, find_jobs, ... One row per button.
    clicks: list[ExtCountRow]
    clickers: int = Field(description="People who pressed anything in the popup.")


class ExtReviewStats(BaseModel):
    """The store-review card in the job panel: shown, and what people chose."""

    asked: int
    asked_users: int
    # By `answer`: review, feedback, later, never. Shown but closed without a choice is the gap.
    answers: list[ExtCountRow]


class ExtAiStats(BaseModel):
    requested: int
    succeeded: int
    failed: int
    limit_hits: int
    by_mode: list[ExtCountRow]
    failures: list[ExtCountRow]
    # From the AI calls log: what the calls cost Rolesetu (own-key calls cost nothing).
    paid_calls: int
    own_key_calls: int
    input_tokens: int
    output_tokens: int


class ExtSiteRow(BaseModel):
    host: str
    users: int
    offered: int
    filled: int
    failed: int
    suggestions_used: int
    ai_answers: int
    fill_rate_pct: int


class ExtErrorRow(BaseModel):
    where: str
    version: str | None
    events: int
    users: int
    last_seen: datetime


class ExtAnalytics(BaseModel):
    """Everything on the admin panel's extension page, for one period."""

    hours: int
    overview: ExtOverview
    versions: list[ExtVersionRow]
    daily: list[ExtDayRow]
    funnel: list[ExtFunnelStep]
    features: list[ExtFeatureRow]
    ai: ExtAiStats
    popup: ExtPopupStats
    reviews: ExtReviewStats
    sites: list[ExtSiteRow]
    errors: list[ExtErrorRow]


class ExtEventRead(BaseModel):
    """One event in a user's timeline."""

    at: datetime
    name: str
    host: str | None
    count: int | None
    version: str | None
    props: dict[str, str | int | bool] | None
