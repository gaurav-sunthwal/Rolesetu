"""Posts to a LinkedIn member's own feed through LinkedIn's official API.

Needs a LinkedIn developer app with two products: "Sign In with LinkedIn using
OpenID Connect" (to learn who connected) and "Share on LinkedIn" (to post).
LinkedIn gives these tokens for 60 days and no refresh token, so an admin
reconnects about every two months; the admin panel warns before it lapses.
"""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from backend.core.config import get_settings
from backend.modules.social.platforms.base import (
    ConnectedAccount,
    PlatformNotConfiguredError,
    Published,
    download_image,
    make_client,
    send,
)

PLATFORM = "LinkedIn"
SCOPES = "openid profile w_member_social"
MAX_TEXT = 3000
_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"  # noqa: S105 - an address
_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
_REST = "https://api.linkedin.com/rest"

# LinkedIn reads post text as its own markup, where these characters mean
# something. Each one is escaped so the text appears exactly as written.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>*_~#])")
_HASHTAG = re.compile(r"(?<![\w#])#([A-Za-z0-9]+)")


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.linkedin_client_id and settings.linkedin_client_secret)


def _credentials() -> tuple[str, str]:
    settings = get_settings()
    if not settings.linkedin_client_id or not settings.linkedin_client_secret:
        raise PlatformNotConfiguredError(PLATFORM)
    return settings.linkedin_client_id, settings.linkedin_client_secret


def consent_url(state: str) -> str:
    client_id, _ = _credentials()
    return f"{_AUTH_URL}?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": get_settings().linkedin_redirect_uri,
            "state": state,
            "scope": SCOPES,
        }
    )


def to_commentary(text: str) -> str:
    """Post text in LinkedIn's markup: literal everywhere, except that
    #words stay real hashtags.
    """
    parts: list[str] = []
    last = 0
    for found in _HASHTAG.finditer(text):
        parts.append(_RESERVED.sub(r"\\\1", text[last : found.start()]))
        parts.append(f"{{hashtag|\\#|{found.group(1)}}}")
        last = found.end()
    parts.append(_RESERVED.sub(r"\\\1", text[last:]))
    return "".join(parts)


async def exchange_code(code: str, now: datetime | None = None) -> list[ConnectedAccount]:
    """Trades the code LinkedIn sent back for a token, and finds whose it is."""
    client_id, client_secret = _credentials()
    now = now or datetime.now(UTC)
    async with make_client() as client:
        token = await send(
            client,
            PLATFORM,
            "POST",
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": get_settings().linkedin_redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        body = token.json()
        access_token = str(body["access_token"])
        expires_in = int(body.get("expires_in", 0)) or 60 * 24 * 3600
        me = await send(
            client,
            PLATFORM,
            "GET",
            _USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    profile = me.json()
    return [
        ConnectedAccount(
            platform="linkedin",
            external_id=str(profile["sub"]),
            name=str(profile.get("name") or "LinkedIn member"),
            access_token=access_token,
            expires_at=now + timedelta(seconds=expires_in),
        )
    ]


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": get_settings().linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }


async def publish(
    *, access_token: str, member_id: str, text: str, image_url: str | None
) -> Published:
    author = f"urn:li:person:{member_id}"
    async with make_client() as client:
        content = None
        if image_url:
            image = await download_image(client, image_url)
            started = await send(
                client,
                PLATFORM,
                "POST",
                f"{_REST}/images?action=initializeUpload",
                headers=_headers(access_token),
                json={"initializeUploadRequest": {"owner": author}},
            )
            upload = started.json()["value"]
            await send(
                client,
                PLATFORM,
                "PUT",
                str(upload["uploadUrl"]),
                headers={"Authorization": f"Bearer {access_token}"},
                content=image,
            )
            content = {"media": {"id": str(upload["image"])}}

        post: dict[str, object] = {
            "author": author,
            "commentary": to_commentary(text),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if content is not None:
            post["content"] = content
        created = await send(
            client,
            PLATFORM,
            "POST",
            f"{_REST}/posts",
            publishes=True,
            headers=_headers(access_token),
            json=post,
        )
    urn = created.headers.get("x-restli-id")
    return Published(url=f"https://www.linkedin.com/feed/update/{urn}/" if urn else None)
