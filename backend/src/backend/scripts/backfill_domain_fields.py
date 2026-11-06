"""One-off: give existing accounts the same field and skill catalog as new ones.

    cd backend && uv run python -m backend.scripts.backfill_domain_fields

Profiles that already have a field are left alone. Everyone else is placed
from their resume when the file can be reread, otherwise from their job titles.
A shared skill catalog is created once for each non-software field that comes up.
"""

import asyncio
import logging

from backend.db.session import get_engine, get_sessionmaker
from backend.modules.profiles.field_backfill import backfill_domain_fields

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    async with get_sessionmaker()() as db:
        notes = await backfill_domain_fields(db)
        await db.commit()
    for note in notes:
        print(note)
    print(f"Done. {len(notes)} lines.")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
