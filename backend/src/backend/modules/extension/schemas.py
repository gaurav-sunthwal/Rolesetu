from datetime import datetime

from pydantic import BaseModel

from backend.modules.profiles.schemas import ProfileRead


class ExtensionConnected(BaseModel):
    # Shown to the dashboard once, to hand to the extension. Never retrievable again.
    token: str
    connected_at: datetime


class ExtensionStatus(BaseModel):
    connected: bool
    connected_at: datetime | None
    last_used_at: datetime | None


class AutofillData(BaseModel):
    """Everything the extension may type into an application form for the user."""

    email: str
    profile: ProfileRead
    # Saved answers by question key, e.g. {"notice_period": "30 days"}.
    saved_answers: dict[str, str]
    # Worked out from the dated roles on the profile.
    years_of_experience: float
