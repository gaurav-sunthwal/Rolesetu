"""Downloads a web page the user pointed us at, safely.

A server that fetches user-supplied links can be tricked into reading things
only it can reach (cloud metadata, admin panels, localhost). So before every
request, including each redirect, the address is resolved and must be a public
internet address. Responses are also capped in size and time.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from backend.core.exceptions import ValidationFailedError

USER_AGENT = "Mozilla/5.0 (compatible; Rolesetu/0.1; job-link reader)"
MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_ALLOWED_PORTS = {None, 80, 443}
PASTE_INSTEAD = "Paste the job description instead."


class PageFetchError(ValidationFailedError):
    """The link could not be read. The message says why, in plain words."""


class PageBlockedError(PageFetchError):
    """The site refused us or did not answer, though the page may well exist.

    Worth a second attempt through a real browser (see rendered_fetch).
    """


async def assert_public(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PageFetchError("That does not look like a web link. It should start with https://")
    if parts.username or parts.password or parts.port not in _ALLOWED_PORTS:
        raise PageFetchError("That link cannot be opened. Use the job page's normal web address.")
    try:
        loop = asyncio.get_running_loop()
        resolved = await loop.getaddrinfo(parts.hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise PageFetchError("That website could not be found. Check the link.") from exc
    for entry in resolved:
        if not ipaddress.ip_address(entry[4][0]).is_global:
            raise PageFetchError("That link points to a private address and cannot be opened.")


def _error_for_status(status: int) -> PageFetchError:
    if status in (401, 403, 429, 999):
        return PageBlockedError(
            "This site does not let us read the page (it may need you to be signed in). "
            f"{PASTE_INSTEAD}"
        )
    if status in (404, 410):
        return PageFetchError("That job page no longer exists. The listing may have been removed.")
    message = f"The site returned an error ({status}) for that link. {PASTE_INSTEAD}"
    return PageBlockedError(message) if status >= 500 else PageFetchError(message)


async def fetch_page(url: str) -> tuple[str, str]:
    """Returns (final_url, html). Raises PageFetchError with a message for the user."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await assert_public(url)
                async with client.stream("GET", url, headers=headers) as response:
                    if response.is_redirect and "location" in response.headers:
                        # Followed by hand, so every hop is checked like the first.
                        url = urljoin(url, response.headers["location"])
                        continue
                    if response.status_code >= 400:
                        raise _error_for_status(response.status_code)
                    content_type = response.headers.get("content-type", "")
                    if "html" not in content_type and "xml" not in content_type:
                        raise PageFetchError(
                            f"That link is not a web page we can read. {PASTE_INSTEAD}"
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            break
                    encoding = response.encoding or "utf-8"
                    return url, bytes(body[:MAX_BYTES]).decode(encoding, errors="replace")
            raise PageFetchError("That link redirects too many times to follow.")
    except httpx.TimeoutException as exc:
        raise PageBlockedError(f"The site took too long to respond. {PASTE_INSTEAD}") from exc
    except httpx.HTTPError as exc:
        raise PageBlockedError(f"We could not reach that site. {PASTE_INSTEAD}") from exc
