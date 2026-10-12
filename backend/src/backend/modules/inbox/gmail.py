"""Talks to Google: the consent flow and reading mail. Read-only.

Plain HTTPS calls, so there is one small file to read instead of an SDK. Every
call has a timeout, and reads are retried when Google is briefly unavailable.
"""

import base64
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.core.config import get_settings
from backend.core.exceptions import AppError

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - an address, not a secret
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_API = "https://gmail.googleapis.com/gmail/v1/users/me"
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_MAX_BODY = 6000
_HREF = re.compile(r"""<a\b[^>]*\bhref=["']([^"']+)["'][^>]*>""", re.I)
_TAGS = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>|<[^>]+>", re.S | re.I)


class GmailNotConfiguredError(AppError):
    status_code = 503
    detail = "Gmail is not set up on this server yet."


class GmailAccessLostError(Exception):
    """Google no longer accepts our token: the user revoked access or it expired."""


class GmailApiOffError(Exception):
    """The Gmail API is not enabled for the Google Cloud project behind our
    credentials. Nothing the user did: the project needs it switched on.
    """


class GmailBusyError(Exception):
    """Gmail asked us to slow down (its per-minute limit for one mailbox)."""


_SLOW_DOWN = re.compile(r"rateLimitExceeded|userRateLimitExceeded|Quota exceeded", re.I)
_API_OFF = re.compile(r"accessNotConfigured|SERVICE_DISABLED|has not been used in project", re.I)


@dataclass(frozen=True)
class RawMail:
    id: str
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    # Read to classify the mail, then discarded. Never stored.
    body: str
    # A calendar invite attached to the mail, if any. Read for the time, then discarded.
    calendar: str | None = None
    # The sender's own timezone, as minutes from UTC, from the mail's Date header.
    sender_offset_minutes: int = 0


class Mailbox(Protocol):
    """What a sync needs from a mailbox. Tests supply a fake one."""

    async def list_ids(self, query: str, limit: int) -> list[str]: ...
    async def read(self, message_id: str) -> RawMail: ...


def _credentials() -> tuple[str, str]:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise GmailNotConfiguredError
    return settings.google_client_id, settings.google_client_secret


def consent_url(state: str) -> str:
    client_id, _ = _credentials()
    return f"{_AUTH_URL}?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": get_settings().google_redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            # "offline" + "consent" is what makes Google hand over a refresh token.
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )


async def _token_request(data: dict[str, str]) -> dict[str, Any]:
    client_id, client_secret = _credentials()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            _TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret, **data}
        )
    if response.status_code in (400, 401):
        raise GmailAccessLostError(response.text[:200])
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body


async def exchange_code(code: str) -> tuple[str, str]:
    """Trades the code Google sent back for (refresh token, access token)."""
    body = await _token_request(
        {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": get_settings().google_redirect_uri,
        }
    )
    if "refresh_token" not in body or SCOPE not in str(body.get("scope", "")):
        raise GmailAccessLostError("Read access to Gmail was not granted.")
    return str(body["refresh_token"]), str(body["access_token"])


async def access_token_for(refresh_token: str) -> str:
    body = await _token_request({"refresh_token": refresh_token, "grant_type": "refresh_token"})
    return str(body["access_token"])


async def revoke(refresh_token: str) -> None:
    """Tells Google to forget the grant. Best effort: disconnecting must not fail on it."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(_REVOKE_URL, params={"token": refresh_token})
    except httpx.HTTPError:
        return


def _retryable(error: BaseException) -> bool:
    if isinstance(error, GmailBusyError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(error, httpx.TransportError)


def _text_of(payload: dict[str, Any]) -> tuple[str, str | None]:
    """The readable text of a mail (its plain part, or its HTML part with the
    tags removed) and the calendar invite attached to it, if there is one.
    """
    plain, rich, invite = "", "", None
    stack = [payload]
    while stack:
        part = stack.pop()
        stack.extend(part.get("parts") or [])
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        text = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
        kind = part.get("mimeType")
        if kind == "text/calendar" and invite is None:
            invite = text[:20000]
        elif kind == "text/plain" and not plain:
            plain = text
        elif kind == "text/html" and not rich:
            # Keep where links point: a "Join meeting" button is only a link.
            rich = html.unescape(_TAGS.sub(" ", _HREF.sub(r" \1 ", text)))
    return re.sub(r"[ \t\r\f\v]+", " ", plain or rich).strip()[:_MAX_BODY], invite


def _offset_minutes(date_header: str) -> int:
    try:
        offset = parsedate_to_datetime(date_header).utcoffset()
    except (TypeError, ValueError):
        return 0
    return int(offset.total_seconds() // 60) if offset else 0


class GmailMailbox:
    """A user's Gmail, for the length of one sync."""

    def __init__(self, access_token: str) -> None:
        self._headers = {"Authorization": f"Bearer {access_token}"}

    @retry(
        retry=retry_if_exception(_retryable),
        # Long enough waits to ride out Gmail's per-minute limit, then give up.
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, max=20),
        reraise=True,
    )
    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(f"{_API}{path}", params=params, headers=self._headers)
        if response.status_code == 403 and _API_OFF.search(response.text):
            raise GmailApiOffError
        # Gmail reports "too fast" as 429 or as a 403, which is not a loss of access.
        if response.status_code == 429 or (
            response.status_code == 403 and _SLOW_DOWN.search(response.text)
        ):
            raise GmailBusyError
        if response.status_code in (401, 403):
            raise GmailAccessLostError(response.text[:200])
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        return body

    async def address(self) -> str:
        return str((await self._get("/profile", {}))["emailAddress"])

    async def list_ids(self, query: str, limit: int) -> list[str]:
        ids: list[str] = []
        page: str | None = None
        while len(ids) < limit:
            params = {"q": query, "maxResults": str(min(100, limit - len(ids)))}
            if page:
                params["pageToken"] = page
            body = await self._get("/messages", params)
            ids += [str(item["id"]) for item in body.get("messages", [])]
            page = body.get("nextPageToken")
            if not page:
                break
        return ids

    async def read(self, message_id: str) -> RawMail:
        body = await self._get(f"/messages/{message_id}", {"format": "full"})
        payload: dict[str, Any] = body.get("payload") or {}
        headers = {
            str(header["name"]).lower(): str(header["value"])
            for header in payload.get("headers", [])
        }
        name, address = parseaddr(headers.get("from", ""))
        text, invite = _text_of(payload)
        return RawMail(
            id=message_id,
            sender_name=(name or address.split("@")[0])[:200],
            sender_email=address.lower()[:320],
            subject=headers.get("subject", "(no subject)")[:500],
            received_at=datetime.fromtimestamp(int(body.get("internalDate", 0)) / 1000, tz=UTC),
            body=text or str(body.get("snippet", "")),
            calendar=invite,
            sender_offset_minutes=_offset_minutes(headers.get("date", "")),
        )
