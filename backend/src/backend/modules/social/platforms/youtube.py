"""Posts Shorts to a YouTube channel through the YouTube Data API.

Connecting signs in with Google once. Google gives a refresh token that does
not expire while the app is "In production" (in "Testing" it lasts 7 days);
it is what we store, encrypted, as the account's token. Each request trades
it for an access token that lasts an hour.

A vertical video under three minutes becomes a Short by itself. Until Google
audits the app, every upload is made private by YouTube and must be switched
to public in YouTube Studio; the upload itself still succeeds.
"""

from urllib.parse import urlencode

import httpx

from backend.core.config import get_settings
from backend.modules.social.platforms.base import (
    ConnectedAccount,
    PlatformNotConfiguredError,
    PostRejectedError,
    Published,
    Stats,
    TokenRejectedError,
    make_client,
    send,
)

PLATFORM = "YouTube"
SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
)
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API = "https://www.googleapis.com/youtube/v3"
_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
# "People & Blogs": YouTube needs a category; this one fits job-hunt content.
_CATEGORY = "22"


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.youtube_client_id and settings.youtube_client_secret)


def _credentials() -> tuple[str, str]:
    settings = get_settings()
    if not settings.youtube_client_id or not settings.youtube_client_secret:
        raise PlatformNotConfiguredError("YouTube")
    return settings.youtube_client_id, settings.youtube_client_secret


def consent_url(state: str) -> str:
    client_id, _ = _credentials()
    return f"{_AUTH_URL}?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": get_settings().youtube_redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            # A refresh token, every time: without `prompt=consent` Google only
            # gives one on the first ever sign-in.
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )


async def _access_token(client: httpx.AsyncClient, refresh_token: str) -> str:
    client_id, client_secret = _credentials()
    response = await client.post(
        _TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if response.status_code in (400, 401):
        # invalid_grant: the sign-in was revoked, or expired (app left in "Testing").
        raise TokenRejectedError(f"{PLATFORM} no longer accepts this connection.")
    if not response.is_success:
        raise PostRejectedError(f"{PLATFORM} sign-in failed ({response.status_code}).")
    return str(response.json()["access_token"])


async def exchange_code(code: str) -> list[ConnectedAccount]:
    """Trades the code for a lasting sign-in, then finds the channel it belongs to."""
    client_id, client_secret = _credentials()
    async with make_client() as client:
        tokens = await send(
            client,
            PLATFORM,
            "POST",
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": get_settings().youtube_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        body = tokens.json()
        refresh_token = body.get("refresh_token")
        if not refresh_token:
            raise PostRejectedError(
                "Google did not give a lasting sign-in. Remove Rolesetu's access in your "
                "Google account settings, then connect again."
            )
        channels = await send(
            client,
            PLATFORM,
            "GET",
            f"{_API}/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
    return [
        ConnectedAccount(
            platform="youtube",
            external_id=str(item["id"]),
            name=str(item.get("snippet", {}).get("title") or "YouTube channel"),
            access_token=str(refresh_token),
            expires_at=None,
        )
        for item in channels.json().get("items", [])
    ]


async def publish(*, refresh_token: str, title: str, description: str, video: bytes) -> Published:
    """Uploads `video` as a public Short (private until Google audits the app)."""
    async with make_client(get_settings().social_upload_timeout_seconds) as client:
        access = await _access_token(client, refresh_token)
        started = await send(
            client,
            PLATFORM,
            "POST",
            _UPLOAD,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access}",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(len(video)),
            },
            json={
                "snippet": {
                    "title": title[:MAX_TITLE],
                    "description": description[:MAX_DESCRIPTION],
                    "categoryId": _CATEGORY,
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            },
        )
        location = started.headers.get("location")
        if not location:
            raise PostRejectedError(f"{PLATFORM} did not start the upload.")
        uploaded = await send(
            client,
            PLATFORM,
            "PUT",
            location,
            publishes=True,
            headers={"Authorization": f"Bearer {access}", "Content-Type": "video/mp4"},
            content=video,
        )
    video_id = str(uploaded.json()["id"])
    return Published(url=f"https://www.youtube.com/shorts/{video_id}", external_id=video_id)


def _count(value: object) -> int | None:
    # YouTube sends counts as strings.
    return int(value) if isinstance(value, str) and value.isdigit() else None


async def stats(*, refresh_token: str, video_id: str) -> Stats:
    async with make_client() as client:
        access = await _access_token(client, refresh_token)
        response = await send(
            client,
            PLATFORM,
            "GET",
            f"{_API}/videos",
            params={"part": "statistics", "id": video_id},
            headers={"Authorization": f"Bearer {access}"},
        )
    items = response.json().get("items", [])
    numbers = items[0].get("statistics", {}) if items else {}
    return Stats(
        views=_count(numbers.get("viewCount")),
        likes=_count(numbers.get("likeCount")),
        comments=_count(numbers.get("commentCount")),
    )


async def subscribers(*, refresh_token: str, channel_id: str) -> int | None:
    async with make_client() as client:
        access = await _access_token(client, refresh_token)
        response = await send(
            client,
            PLATFORM,
            "GET",
            f"{_API}/channels",
            params={"part": "statistics", "id": channel_id},
            headers={"Authorization": f"Bearer {access}"},
        )
    items = response.json().get("items", [])
    return _count(items[0].get("statistics", {}).get("subscriberCount")) if items else None
