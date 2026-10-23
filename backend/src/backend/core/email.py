"""Sends email. The only place that talks to a mail service, so the provider
can be changed here without touching the code that writes the emails.

Two providers, tried in this order:
- Gmail: sends from one Gmail account through the Gmail API (free, about 500
  recipients a day). Used while Rolesetu has no domain of its own.
- Resend: needs a domain verified in Resend; kept for when there is one.
With neither set up, nothing is sent and the callers carry on.
"""

import base64
import logging
import time
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

# A Gmail access token lasts an hour. It is kept in memory and fetched again
# shortly before it runs out; each server instance holding its own is fine.
_gmail_token: tuple[str, float] | None = None


def _uses_gmail(settings: Settings) -> bool:
    return bool(
        settings.gmail_sender_refresh_token
        and settings.google_client_id
        and settings.google_client_secret
    )


def is_configured() -> bool:
    """Whether any email can be sent at all."""
    settings = get_settings()
    return _uses_gmail(settings) or bool(settings.resend_api_key)


def _worth_retrying(error: BaseException) -> bool:
    """A dropped connection, a rate limit or a fault on the provider's side may
    pass. A refusal (bad key, address not allowed) will be the same next time.
    """
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return isinstance(error, httpx.TransportError)


@retry(
    retry=retry_if_exception(_worth_retrying),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=8),
    reraise=True,
)
async def send_email(
    *,
    to: str,
    subject: str,
    html: str | None,
    text: str,
    idempotency_key: str,
    sender_name: str | None = None,
) -> None:
    """Sends one email, or raises. Does nothing when no provider is set up.

    `html` None sends plain text only, which reads like a note typed by a
    person. `sender_name` replaces the name in front of EMAIL_FROM's address.

    `idempotency_key` names this email. Resend sends it once however many
    times it is asked; Gmail has no such promise, so callers that must never
    send twice also record the send themselves.
    """
    settings = get_settings()
    sender = settings.email_from
    if sender_name:
        sender = formataddr((sender_name, parseaddr(sender)[1]))
    async with httpx.AsyncClient(timeout=settings.email_timeout_seconds) as client:
        if _uses_gmail(settings):
            await _send_with_gmail(
                client, settings, sender=sender, to=to, subject=subject, html=html, text=text
            )
        elif settings.resend_api_key:
            await _send_with_resend(
                client,
                settings,
                sender=sender,
                to=to,
                subject=subject,
                html=html,
                text=text,
                idempotency_key=idempotency_key,
            )


async def _gmail_access_token(client: httpx.AsyncClient, settings: Settings) -> str:
    global _gmail_token
    if _gmail_token is not None and _gmail_token[1] > time.monotonic() + 60:
        return _gmail_token[0]
    response = await client.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": settings.gmail_sender_refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if response.status_code == 400:
        # Usually "invalid_grant": the sign-in was revoked, or the Google Cloud
        # app is still in Testing (its sign-ins expire after 7 days).
        logger.error(
            "Gmail sender sign-in was refused (%s). Run `python -m "
            "backend.scripts.gmail_sender_token` again and update GMAIL_SENDER_REFRESH_TOKEN.",
            response.json().get("error", "unknown"),
        )
    response.raise_for_status()
    data = response.json()
    _gmail_token = (str(data["access_token"]), time.monotonic() + float(data["expires_in"]))
    return _gmail_token[0]


async def _send_with_gmail(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    sender: str,
    to: str,
    subject: str,
    html: str | None,
    text: str,
) -> None:
    message = EmailMessage()
    # Gmail only keeps this address if it is the signed-in account (or one of
    # its "send as" addresses); the name in front of it is always kept.
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    if settings.email_reply_to:
        message["Reply-To"] = settings.email_reply_to
    message.set_content(text)
    if html is not None:
        message.add_alternative(html, subtype="html")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    token = await _gmail_access_token(client, settings)
    response = await client.post(
        GMAIL_SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()


async def _send_with_resend(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    sender: str,
    to: str,
    subject: str,
    html: str | None,
    text: str,
    idempotency_key: str,
) -> None:
    body: dict[str, object] = {"from": sender, "to": [to], "subject": subject, "text": text}
    if html is not None:
        body["html"] = html
    if settings.email_reply_to:
        body["reply_to"] = settings.email_reply_to
    response = await client.post(
        RESEND_URL,
        json=body,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Idempotency-Key": idempotency_key,
        },
    )
    response.raise_for_status()
