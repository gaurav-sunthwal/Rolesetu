"""What every social platform client shares: its result types, its errors,
and one place that makes HTTP clients (tests swap it for a fake transport).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from backend.core.config import get_settings
from backend.core.exceptions import AppError

MAX_IMAGE_BYTES = 8 * 1024 * 1024


class PlatformNotConfiguredError(AppError):
    status_code = 503

    def __init__(self, platform: str) -> None:
        super().__init__(f"{platform} is not set up on this server yet. Add its app keys first.")


class PostRejectedError(Exception):
    """The platform refused, and asking again will not help. The message is
    safe to show an admin: it never holds a token.
    """


class TokenRejectedError(PostRejectedError):
    """The platform no longer accepts our token. The account must be reconnected."""


class PlatformBusyError(Exception):
    """The platform failed before doing anything (down, or asked us to slow
    down). Safe to try again later: nothing was posted.
    """


class OutcomeUnknownError(PostRejectedError):
    """The platform stopped answering mid-request. The post may or may not be
    up, so it is never retried on its own (that could post it twice).
    """


@dataclass(frozen=True)
class ConnectedAccount:
    platform: str
    external_id: str
    name: str
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class Published:
    url: str | None


def make_client() -> httpx.AsyncClient:
    seconds = get_settings().social_timeout_seconds
    return httpx.AsyncClient(timeout=httpx.Timeout(seconds, connect=5.0))


def platform_message(body: Any) -> str | None:
    """The platform's own explanation from an error body, if it gave one."""
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return str(error["message"])
    for key in ("message", "error_description"):
        if isinstance(body.get(key), str):
            return str(body[key])
    return None


def raise_for_response(response: httpx.Response, platform: str) -> None:
    if response.is_success:
        return
    try:
        body = response.json()
    except ValueError:
        body = None
    reason = (platform_message(body) or response.reason_phrase or "no reason given")[:300]
    # Meta reports a dead token as code 190, sometimes with status 400.
    meta_code = body.get("error", {}).get("code") if isinstance(body, dict) else None
    if response.status_code == 401 or meta_code == 190:
        raise TokenRejectedError(f"{platform} no longer accepts this connection: {reason}")
    if response.status_code == 429 or response.status_code >= 500:
        raise PlatformBusyError(f"{platform} is busy ({response.status_code}): {reason}")
    raise PostRejectedError(f"{platform} refused the post: {reason}")


async def send(
    client: httpx.AsyncClient,
    platform: str,
    method: str,
    url: str,
    *,
    publishes: bool = False,
    **kwargs: Any,
) -> httpx.Response:
    """One request, with failures sorted into the errors above. `publishes`
    marks the request that makes the post public: if that one is cut off, we
    cannot tell whether it went through.
    """
    try:
        response = await client.request(method, url, **kwargs)
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise PlatformBusyError(f"Could not reach {platform}.") from exc
    except httpx.HTTPError as exc:
        if not publishes:
            raise PlatformBusyError(f"{platform} did not answer in time.") from exc
        raise OutcomeUnknownError(
            f"{platform} stopped answering mid-request. Check the account before trying again, "
            "the post may already be up."
        ) from exc
    raise_for_response(response, platform)
    return response


async def download_image(client: httpx.AsyncClient, url: str) -> bytes:
    """Reads a post's image, for platforms that want the bytes rather than a link."""
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise PostRejectedError("The post's image could not be downloaded.") from exc
    if not response.is_success:
        raise PostRejectedError(
            f"The post's image could not be downloaded ({response.status_code})."
        )
    if len(response.content) > MAX_IMAGE_BYTES:
        raise PostRejectedError("The post's image is larger than 8 MB.")
    return response.content
