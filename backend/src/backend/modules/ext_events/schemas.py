from typing import Literal

from pydantic import BaseModel, Field

EventName = Literal[
    "autofill_offered",
    "autofill_filled",
    "autofill_failed",
    "autofill_learned",
    "job_scored",
    "panel_opened",
    "apply_clicked",
]


class ExtEventWrite(BaseModel):
    """One event sent from the extension."""

    name: EventName
    # Hostname only — the extension strips the path before sending.
    host: str | None = Field(None, max_length=120)
    # Meaning depends on the event: fields filled, match score, etc.
    count: int | None = Field(None, ge=0, le=100_000)


class ExtEventsWrite(BaseModel):
    """A micro-batch: up to 20 events in one request."""

    events: list[ExtEventWrite] = Field(..., min_length=1, max_length=20)


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
