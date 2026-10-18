"""Collects jobs once a day, from inside the API.

Every server checks once an hour whether a collection is due. The first to
take the lease in the database does it; the others see the lease and wait for
the next hour. A run that fails gives the lease back, so the next check tries
again instead of waiting a day.
"""

import asyncio
import logging
from datetime import timedelta

from backend.db.session import get_sessionmaker
from backend.modules.career_jobs import store
from backend.modules.career_jobs.collect import collect, current_audience, everyone_to_read

logger = logging.getLogger(__name__)

CHECK_EVERY = timedelta(hours=1)
# A little under a day, so the run drifts no later from one day to the next.
COLLECT_EVERY = timedelta(hours=20)
# Longer than a run takes (a few minutes); a server that dies mid-run frees it by then.
LEASE = timedelta(minutes=45)
# Let the server finish starting before the first check.
_FIRST_CHECK_AFTER_SECONDS = 60


async def run_if_due() -> bool:
    """Collects if a collection is due and no other server is collecting.
    True when this server did the collecting."""
    sessions = get_sessionmaker()
    async with sessions() as db:
        if not await store.is_due(db, COLLECT_EVERY) or not await store.take_lease(db, LEASE):
            await db.commit()
            return False
        await db.commit()
    try:
        audience = await current_audience()
        companies = await everyone_to_read()
        result = await asyncio.wait_for(
            collect(companies, audience=audience),
            timeout=(LEASE - timedelta(minutes=5)).total_seconds(),
        )
    except BaseException:
        async with sessions() as db:
            await store.release(db)
            await db.commit()
        raise
    async with sessions() as db:
        await store.finish(db)
        await db.commit()
    failed = sum(1 for company in result.companies.values() if company.error)
    logger.info(
        "career jobs collected companies=%d failed=%d jobs=%d",
        len(result.companies),
        failed,
        sum(len(jobs) for jobs in result.jobs.values()),
    )
    return True


async def keep_collecting() -> None:
    """Runs for as long as the server does."""
    await asyncio.sleep(_FIRST_CHECK_AFTER_SECONDS)
    while True:
        try:
            await run_if_due()
        except asyncio.CancelledError:
            raise
        except Exception:  # A failed run must not stop tomorrow's.
            logger.exception("career jobs collection failed")
        await asyncio.sleep(CHECK_EVERY.total_seconds())
