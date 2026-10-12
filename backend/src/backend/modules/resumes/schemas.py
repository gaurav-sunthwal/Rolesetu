import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from backend.modules.profiles.schemas import ProfileRead, ProfileWrite

ResumeStatus = Literal["processing", "parsed", "failed"]


class ResumeRead(BaseModel):
    id: uuid.UUID
    filename: str
    size_bytes: int
    status: ResumeStatus
    error: str | None
    # What was read from the file, ready to go onto the profile.
    parsed: ProfileWrite | None
    applied_at: datetime | None
    created_at: datetime


class ResumeApply(BaseModel):
    mode: Literal["merge", "replace"] = "merge"


class ResumeApplied(BaseModel):
    resume: ResumeRead
    profile: ProfileRead


class DownloadLink(BaseModel):
    url: str
    expires_in: int
