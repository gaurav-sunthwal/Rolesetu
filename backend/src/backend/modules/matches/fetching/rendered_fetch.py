"""Reads a page through Context.dev, which loads it in a real browser.

Some job boards answer a plain request with a block page, or build the listing
with JavaScript, so our own fetch gets nothing usable. Context.dev renders the
page and hands back its HTML. Every call spends a paid credit, so this is only
the second attempt, after safe_fetch has failed.
"""

import logging
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from backend.core.config import get_settings
from backend.modules.matches.fetching.safe_fetch import MAX_BYTES

logger = logging.getLogger(__name__)

API_URL = "https://api.context.dev/v1/web/scrape"
# A key that is wrong, out of credits or rate limited: the next key is tried.
_KEY_REFUSED = {401, 403, 429}


class _Output(BaseModel):
    success: bool = False
    data: str | None = None
    error_code: str | None = None


class _ScrapeResponse(BaseModel):
    html: _Output = _Output()


def is_configured() -> bool:
    return bool(get_settings().context_api_keys)


async def fetch_rendered(url: str) -> str | None:
    """The page's HTML as a browser shows it, or None when it could not be read.

    The caller must already have checked that the link is a public address.
    """
    settings = get_settings()
    deadline = settings.context_timeout_seconds
    host = urlsplit(url).hostname
    body = {
        "url": url,
        "formats": {"html": True},
        "timeoutOpts": {"milliseconds": int(deadline * 1000), "behavior": "fail"},
    }
    # Longer than the deadline we give Context.dev, so its answer is not cut off.
    async with httpx.AsyncClient(timeout=deadline + 5) as client:
        for position, key in enumerate(settings.context_api_keys, start=1):
            try:
                response = await client.post(
                    API_URL, json=body, headers={"Authorization": f"Bearer {key}"}
                )
            except httpx.HTTPError as exc:
                logger.warning("rendered fetch failed host=%s error=%s", host, type(exc).__name__)
                return None
            if response.status_code in _KEY_REFUSED:
                logger.warning(
                    "rendered fetch key refused key=%d status=%d", position, response.status_code
                )
                continue
            if response.status_code != 200:
                logger.warning(
                    "rendered fetch failed host=%s status=%d", host, response.status_code
                )
                return None
            try:
                output = _ScrapeResponse.model_validate_json(response.content).html
            except ValidationError:
                logger.warning("rendered fetch gave an unexpected response host=%s", host)
                return None
            if not output.success or not output.data:
                logger.info("rendered fetch empty host=%s code=%s", host, output.error_code)
                return None
            logger.info("rendered fetch ok host=%s key=%d", host, position)
            return output.data[:MAX_BYTES]
    logger.error("rendered fetch: every Context.dev key was refused")
    return None
