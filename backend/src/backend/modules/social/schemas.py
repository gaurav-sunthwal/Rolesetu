import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

Platform = Literal["linkedin", "facebook", "instagram"]
# The login a platform's "Connect" button starts: Meta's covers Facebook and Instagram.
Provider = Literal["linkedin", "meta"]
PostStatus = Literal["draft", "scheduled", "publishing", "posted", "partly_posted", "failed"]
TargetStatus = Literal["pending", "publishing", "posted", "failed"]


def _public_https(url: str) -> str:
    if not url.startswith("https://"):
        raise ValueError("The image link must start with https:// so the platforms can fetch it.")
    return url


class ProviderStatus(BaseModel):
    provider: Provider
    # False until the platform's app keys are set on the server.
    configured: bool


class SocialAccountRead(BaseModel):
    id: uuid.UUID
    platform: Platform
    name: str
    status: Literal["active", "expired"]
    expires_at: datetime | None
    connected_by: str
    created_at: datetime


class SocialOverview(BaseModel):
    providers: list[ProviderStatus]
    accounts: list[SocialAccountRead]


class ConnectUrl(BaseModel):
    url: str


class ImageUploaded(BaseModel):
    url: str


class SocialPostWrite(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]
    image_url: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, max_length=2000),
            AfterValidator(_public_https),
        ]
        | None
    ) = None
    account_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class ScheduleRequest(BaseModel):
    # None, or a time already past, means now.
    at: datetime | None = None


class SocialTargetRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    platform: Platform
    account_name: str
    status: TargetStatus
    external_url: str | None
    error: str | None
    posted_at: datetime | None


class SocialPostRead(BaseModel):
    id: uuid.UUID
    text: str
    image_url: str | None
    status: PostStatus
    scheduled_at: datetime | None
    created_by: str
    approved_by: str | None
    created_at: datetime
    targets: list[SocialTargetRead]
