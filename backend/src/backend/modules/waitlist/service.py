"""The list of people to email when the browser extension is released."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import hash_ip
from backend.core.exceptions import RateLimitedError
from backend.modules.waitlist import repository

# Addresses one visitor can add in an hour. Enough for a household, not for a script.
MAX_JOINS_PER_HOUR = 5


async def join(db: AsyncSession, *, email: str, client_ip: str) -> None:
    client_hash = hash_ip(client_ip)
    since = datetime.now(UTC) - timedelta(hours=1)
    if await repository.count_by_client(db, client_hash, since) >= MAX_JOINS_PER_HOUR:
        raise RateLimitedError("Too many sign-ups from here in the last hour. Try again later.")
    await repository.add_if_new(db, email.strip().lower(), client_hash)
