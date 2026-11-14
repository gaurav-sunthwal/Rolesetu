"""Following an install from the moment it happens, before anyone signs in.

The extension and the website's setup pages report steps here without an account,
so these limits keep a script from filling the tables.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import hash_ip
from backend.core.exceptions import RateLimitedError
from backend.modules.ext_installs import repository
from backend.modules.ext_installs.schemas import InstallEventsWrite

# New installs one address can register in an hour: a guard against a script
# flooding the table, set high because requests may reach the API through the
# website's proxy, where many people can share one address.
MAX_NEW_INSTALLS_PER_HOUR = 200
# Steps one install can report in a day, far above any real setup.
MAX_EVENTS_PER_DAY = 300


async def record(db: AsyncSession, payload: InstallEventsWrite, client_ip: str) -> None:
    now = datetime.now(UTC)
    install = payload.install
    client_hash = hash_ip(client_ip)
    if await repository.get(db, install.id) is None:
        recent = await repository.count_new_by_client(db, client_hash, now - timedelta(hours=1))
        if recent >= MAX_NEW_INSTALLS_PER_HOUR:
            raise RateLimitedError("Too many new installs from here. Try again later.")
    info = install.model_dump(exclude={"id"})
    await repository.save(db, install.id, {**info, "client_hash": client_hash}, now)

    if not payload.events:
        return
    sent_today = await repository.count_events(db, install.id, now - timedelta(days=1))
    if sent_today + len(payload.events) > MAX_EVENTS_PER_DAY:
        raise RateLimitedError("Too many events from this install today.")
    await repository.insert_events(
        db,
        install.id,
        [
            {
                "name": event.name,
                "host": event.host,
                "count": event.count,
                # The website's pages may send none: one is made so the row is still unique.
                "client_id": event.id or str(uuid.uuid4()),
                "version": event.version or install.version,
                "props": event.props,
                "created_at": event.happened_at(now) or now,
            }
            for event in payload.events
        ],
    )


async def link(db: AsyncSession, install_id: str, user_id: uuid.UUID) -> None:
    await repository.link_to_user(db, install_id, user_id, datetime.now(UTC))


async def uninstalled(db: AsyncSession, install_id: str, version: str | None) -> None:
    """Chrome opened the uninstall page for this install. Recorded once."""
    now = datetime.now(UTC)
    installed_at = await repository.mark_uninstalled(db, install_id, now)
    if installed_at is None:
        return
    minutes = int((now - installed_at).total_seconds() // 60)
    await repository.insert_events(
        db,
        install_id,
        [
            {
                "name": "extension_uninstalled",
                "client_id": str(uuid.uuid4()),
                "count": max(minutes, 0),
                "version": version,
                "created_at": now,
            }
        ],
    )
