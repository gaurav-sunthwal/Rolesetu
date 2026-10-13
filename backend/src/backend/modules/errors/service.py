"""Keeps a record of what went wrong, for the admin panel's Errors page.

Recording must never make things worse: it runs in its own database session,
swallows its own failures, stops writing when one problem repeats too fast, and
forgets events after a month.
"""

import hashlib
import logging
import traceback
from datetime import UTC, datetime, timedelta

from backend.db.session import get_sessionmaker
from backend.modules.errors import repository
from backend.modules.errors.models import ErrorEvent

logger = logging.getLogger(__name__)

KEEP_FOR = timedelta(days=30)
# One problem is written at most this often; past it, more rows would say nothing new.
MAX_PER_HOUR = 100
_MESSAGE_LIMIT = 1000
_STACK_LIMIT = 8000


def _where_raised(exc: BaseException) -> str:
    """The innermost place in our own code the error passed through."""
    ours = [
        frame
        for frame in traceback.extract_tb(exc.__traceback__)
        if "/backend/" in frame.filename and "/site-packages/" not in frame.filename
    ]
    if not ours:
        return ""
    last = ours[-1]
    return f"{last.filename.rsplit('/backend/', 1)[-1]}:{last.name}"


def _fingerprint(*parts: str | None) -> str:
    return hashlib.sha256("|".join(part or "" for part in parts).encode()).hexdigest()[:32]


async def record(
    *,
    source: str,
    message: str,
    level: str = "error",
    exc: BaseException | None = None,
    route: str | None = None,
    method: str | None = None,
    status: int | None = None,
) -> None:
    """Writes one event. Never raises."""
    code = type(exc).__name__ if exc is not None else None
    # Without an exception the message itself tells problems apart.
    place = _where_raised(exc) if exc is not None else message[:120]
    fingerprint = _fingerprint(source, code, route, place)
    stack = (
        "".join(traceback.format_exception(exc))[-_STACK_LIMIT:]
        if exc is not None and level == "error"
        else None
    )
    try:
        async with get_sessionmaker()() as db:
            now = datetime.now(UTC)
            recent = await repository.count_for(db, fingerprint, now - timedelta(hours=1))
            if recent >= MAX_PER_HOUR:
                return
            db.add(
                ErrorEvent(
                    source=source,
                    level=level,
                    fingerprint=fingerprint,
                    route=route,
                    method=method,
                    status=status,
                    code=code,
                    message=message[:_MESSAGE_LIMIT],
                    stack=stack,
                )
            )
            await repository.delete_older_than(db, now - KEEP_FOR)
            await db.commit()
    except Exception:
        logger.exception("Could not record an error event")
