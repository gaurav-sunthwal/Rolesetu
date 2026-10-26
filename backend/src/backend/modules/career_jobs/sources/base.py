"""What every careers-site reader returns, and the HTTP client they share."""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.modules.matches.fetching.job_page import html_to_text

logger = logging.getLogger(__name__)

# Careers APIs answer browsers; some refuse anything that does not look like one.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT = httpx.Timeout(25.0, connect=10.0)
# Requests in flight to one site at a time. Low on purpose: we are a guest.
PER_HOST = 4
_RETRY_STATUS = {429, 500, 502, 503, 504}


class SourceError(Exception):
    """A careers site answered with something its reader does not understand."""


@dataclass(frozen=True)
class Posting:
    # The site's own id for the job, unique within one company.
    source_id: str
    title: str
    url: str
    location: str
    # None when the site does not say; the day we first saw it is used instead.
    posted_on: date | None
    # Plain text. None when the list leaves it out and `Reader.complete` fetches it.
    description: str | None = None

    def with_description(self, markup: str | None) -> "Posting":
        return replace(self, description=to_text(markup))


class Reader(Protocol):
    async def recent(self, http: "Http", since: date) -> list[Posting]:
        """Jobs in India posted on or after `since` (and undated ones)."""
        ...

    async def complete(self, http: "Http", posting: Posting) -> Posting | None:
        """The posting with its description, or None if it turned out not to be
        in India. Readers whose list already carries the text return it as is.
        """
        ...


class ListOnly:
    """For readers whose list already holds everything."""

    async def complete(self, http: "Http", posting: Posting) -> Posting | None:
        return posting


def to_text(markup: str | None) -> str | None:
    if not markup:
        return None
    return html_to_text(markup).strip() or None


def from_timestamp(seconds: float) -> date:
    return datetime.fromtimestamp(seconds, tz=UTC).date()


def _worth_retrying(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRY_STATUS
    return isinstance(exc, httpx.TransportError)


class Http:
    """One client for a whole run: retries, timeouts and a per-site limit."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._gates: dict[str, asyncio.Semaphore] = {}

    async def _send(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        gate = self._gates.setdefault(host, asyncio.Semaphore(PER_HOST))
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en"}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, max=10),
            retry=retry_if_exception(_worth_retrying),
            reraise=True,
        ):
            with attempt:
                async with gate:
                    response = await self._client.request(
                        method, url, params=params, json=json, headers=headers
                    )
                response.raise_for_status()
        return response

    async def get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        response = await self._send("GET", url, params=params)
        return _json(response)

    async def post_json(self, url: str, body: Any) -> Any:
        response = await self._send("POST", url, json=body)
        return _json(response)

    async def get_text(self, url: str, params: Mapping[str, Any] | None = None) -> str:
        response = await self._send("GET", url, params=params, accept="text/html,*/*")
        return response.text


def _json(response: httpx.Response) -> Any:
    # Platforms send every request to a status page during their maintenance windows.
    if "maintenance" in response.url.path.lower():
        raise SourceError(f"{response.request.url.host} is down for maintenance; try later")
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError(f"{response.url.host} did not answer with JSON") from exc


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
