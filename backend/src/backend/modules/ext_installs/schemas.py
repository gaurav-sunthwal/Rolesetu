from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.modules.ext_events.schemas import ExtEventWrite, InstallId

_Short = Annotated[str, StringConstraints(max_length=20, pattern=r"^[\w .()/-]*$")]


class InstallInfo(BaseModel):
    """What an install says about itself. Everything but the id is optional: the
    website's setup pages know only the id (from the link the extension opened)."""

    id: InstallId
    version: Annotated[str, StringConstraints(pattern=r"^[0-9][0-9.]{0,19}$")] | None = None
    browser: Annotated[str, StringConstraints(max_length=40, pattern=r"^[\w .()/-]*$")] | None = (
        None
    )
    os: _Short | None = None
    arch: _Short | None = None
    language: _Short | None = None
    timezone: Annotated[str, StringConstraints(max_length=50, pattern=r"^[\w/+-]*$")] | None = None
    automated: bool | None = None


class InstallEventsWrite(BaseModel):
    """Sent without signing in: an install's steps before it is connected."""

    install: InstallInfo
    events: list[ExtEventWrite] = Field(default_factory=list, max_length=50)


# ── Admin ─────────────────────────────────────────────────────────────────────


class InstallStep(BaseModel):
    step: str
    label: str
    installs: int


class InstallGroupRow(BaseModel):
    label: str
    installs: int
    connected: int


class InstallRow(BaseModel):
    install_id: str
    installed_at: datetime
    last_seen_at: datetime
    version: str | None
    browser: str | None
    os: str | None
    language: str | None
    timezone: str | None
    automated: bool | None
    # Other installs from the same address in the period: many means one machine.
    same_address: int
    reached: str
    user_id: str | None
    uninstalled_at: datetime | None


class InstallStats(BaseModel):
    """GET /admin/ext-installs: what happens to new installs in the period."""

    hours: int
    installs: int
    connected: int
    uninstalled: int
    # Never reported anything after the install itself: no setup page, no use.
    silent: int
    automated: int
    # Installs from an address that made 3 or more installs in the period.
    crowded: int
    funnel: list[InstallStep]
    by_os: list[InstallGroupRow]
    by_browser: list[InstallGroupRow]
    by_language: list[InstallGroupRow]
    by_timezone: list[InstallGroupRow]
    by_version: list[InstallGroupRow]
    uninstall_reasons: list[InstallGroupRow]
    recent: list[InstallRow]
