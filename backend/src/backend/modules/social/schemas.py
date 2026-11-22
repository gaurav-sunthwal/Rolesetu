import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from backend.modules.social import videos

Platform = Literal["linkedin", "facebook", "instagram", "youtube"]
# The login a platform's "Connect" button starts: Meta's covers Facebook and Instagram.
Provider = Literal["linkedin", "meta", "youtube"]
# Which posts a list shows: the queue (not yet up everywhere) or what is posted.
PostView = Literal["all", "queue", "posted"]
PostStatus = Literal["draft", "scheduled", "publishing", "posted", "partly_posted", "failed"]
TargetStatus = Literal["pending", "publishing", "posted", "failed"]


def _public_https(url: str) -> str:
    if not url.startswith("https://"):
        raise ValueError("The image link must start with https:// so the platforms can fetch it.")
    return url


def _video_key(key: str) -> str:
    if not videos.KEY.match(key):
        raise ValueError("Upload the video first; this is not a stored video.")
    return key


def _no_angle_brackets(title: str) -> str:
    if "<" in title or ">" in title:
        raise ValueError("YouTube titles cannot contain < or >.")
    return title


class ProviderStatus(BaseModel):
    provider: Provider
    # False until the platform's app keys are set on the server.
    configured: bool


class SocialAccountRead(BaseModel):
    id: uuid.UUID
    platform: Platform
    name: str
    status: Literal["active", "expired"]
    followers: int | None
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


class VideoUploadRequest(BaseModel):
    size_bytes: int = Field(gt=0)


class VideoUploadUrl(BaseModel):
    key: str
    # PUT the file here with Content-Type: video/mp4, then confirm the key.
    upload_url: str


class VideoConfirm(BaseModel):
    key: Annotated[str, AfterValidator(_video_key)]


class VideoUploaded(BaseModel):
    # What a post stores; the link is a preview that stops working after a few hours.
    key: str
    url: str
    size_bytes: int


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
    video_key: Annotated[str, AfterValidator(_video_key)] | None = None
    youtube_title: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
            AfterValidator(_no_angle_brackets),
        ]
        | None
    ) = None
    youtube_description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None
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
    views: int | None
    reach: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    avg_watch_ms: int | None
    metrics_at: datetime | None


class SocialPostRead(BaseModel):
    id: uuid.UUID
    text: str
    image_url: str | None
    video_key: str | None
    # A preview link, good for a few hours.
    video_url: str | None
    youtube_title: str | None
    youtube_description: str | None
    status: PostStatus
    scheduled_at: datetime | None
    created_by: str
    approved_by: str | None
    created_at: datetime
    targets: list[SocialTargetRead]


class PlatformTotals(BaseModel):
    platform: Platform
    posts: int
    views: int
    reach: int
    likes: int
    comments: int
    shares: int
    saves: int
    # Views-weighted average across posts that report it (Instagram reels).
    avg_watch_seconds: float | None


class SocialStats(BaseModel):
    days: int
    platforms: list[PlatformTotals]
    accounts: list[SocialAccountRead]
    # When the numbers were last read from the platforms.
    refreshed_at: datetime | None


class RefreshStarted(BaseModel):
    started: bool
