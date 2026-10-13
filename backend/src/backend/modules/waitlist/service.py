"""The list of people to email when the browser extension is released."""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import hash_ip
from backend.core.config import get_settings
from backend.core.email import send_email
from backend.core.exceptions import RateLimitedError
from backend.modules.waitlist import emails, repository

logger = logging.getLogger(__name__)

# Addresses one visitor can add in an hour. Enough for a household, not for a script.
MAX_JOINS_PER_HOUR = 5


async def join(db: AsyncSession, *, email: str, client_ip: str) -> str | None:
    """Puts the address on the list. Returns it when it was new, which is when
    it is owed a welcome email; an address already listed gets no second one.
    """
    client_hash = hash_ip(client_ip)
    since = datetime.now(UTC) - timedelta(hours=1)
    if await repository.count_by_client(db, client_hash, since) >= MAX_JOINS_PER_HOUR:
        raise RateLimitedError("Too many sign-ups from here in the last hour. Try again later.")
    address = email.strip().lower()
    return address if await repository.add_if_new(db, address, client_hash) else None


async def send_welcome(address: str) -> None:
    """Tells someone they are on the list. Runs after the reply has gone out, so
    a slow or failing mail service never holds up or breaks the sign-up: they
    are on the list either way.
    """
    message = emails.welcome(get_settings().dashboard_url)
    try:
        await send_email(
            to=address,
            subject=message.subject,
            html=message.html,
            text=message.text,
            idempotency_key=f"waitlist-welcome-{hashlib.sha256(address.encode()).hexdigest()}",
        )
    except Exception:
        # The address is left out of the log on purpose.
        logger.exception("Waiting list welcome email was not sent")
