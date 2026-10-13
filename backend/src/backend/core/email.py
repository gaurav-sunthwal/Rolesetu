"""Sends email through Resend. The only place that talks to it, so the
provider can be changed here without touching the code that writes the emails.
"""

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.core.config import get_settings

API_URL = "https://api.resend.com/emails"


def _worth_retrying(error: BaseException) -> bool:
    """A dropped connection, a rate limit or a fault on Resend's side may pass.
    A refusal (bad key, address not allowed) will be the same next time.
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
async def send_email(*, to: str, subject: str, html: str, text: str, idempotency_key: str) -> None:
    """Sends one email, or raises. Does nothing when no Resend key is set.

    `idempotency_key` names this email: Resend sends it once however many
    times it is asked, so a retry can never deliver a second copy.
    """
    settings = get_settings()
    if not settings.resend_api_key:
        return
    body: dict[str, object] = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if settings.email_reply_to:
        body["reply_to"] = settings.email_reply_to
    async with httpx.AsyncClient(timeout=settings.email_timeout_seconds) as client:
        response = await client.post(
            API_URL,
            json=body,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Idempotency-Key": idempotency_key,
            },
        )
    response.raise_for_status()
