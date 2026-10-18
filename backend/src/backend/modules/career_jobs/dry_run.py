"""Reads every company in the catalog and prints what it found. Nothing is saved.

uv run python -m backend.modules.career_jobs.dry_run
uv run python -m backend.modules.career_jobs.dry_run --only accenture amazon --describe 3
"""

import argparse
import asyncio
import time
from datetime import date, timedelta

from backend.modules.career_jobs.catalog import COMPANIES, Company
from backend.modules.career_jobs.places import cities_in
from backend.modules.career_jobs.sources import build_reader
from backend.modules.career_jobs.sources.base import Http, Posting, new_client
from backend.modules.matches.local.experience import read_experience


def _years(posting: Posting) -> str:
    asked = read_experience(posting.description or "", posting.title)
    if asked.source is None:
        return "experience not stated"
    if asked.source == "fresher":
        return "fresher"
    upper = f"-{asked.max_years:g}" if asked.max_years is not None else "+"
    return f"{asked.min_years or 0:g}{upper} yrs ({asked.source})"


async def _one(http: Http, company: Company, since: date, describe: int) -> list[str]:
    reader = build_reader(company.kind, company.config)
    started = time.monotonic()
    try:
        postings = await reader.recent(http, since)
    except Exception as exc:  # A report: one broken site must not hide the rest.
        return [f"✗ {company.name:24} {type(exc).__name__}: {str(exc)[:120]}"]
    took = time.monotonic() - started
    lines = [f"✓ {company.name:24} {len(postings):5} jobs in {took:5.1f}s"]
    for posting in postings[:describe]:
        try:
            complete = await reader.complete(http, posting)
        except Exception as exc:
            lines.append(f"    ! {posting.title[:60]}: {type(exc).__name__}")
            continue
        if complete is None:
            lines.append(f"    - {posting.title[:60]}: not in India")
            continue
        cities = ", ".join(cities_in(complete.location)) or complete.location[:40]
        size = len(complete.description or "")
        lines.append(
            f"    · {complete.title[:55]:55} | {cities[:30]:30} | {complete.posted_on} | "
            f"{_years(complete)} | {size} chars"
        )
    return lines


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="company slugs")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--describe", type=int, default=2, help="jobs per company to read fully")
    args = parser.parse_args()

    companies = [c for c in COMPANIES if not args.only or c.slug in args.only]
    since = date.today() - timedelta(days=args.days)
    async with new_client() as client:
        http = Http(client)
        gate = asyncio.Semaphore(6)

        async def run(company: Company) -> list[str]:
            async with gate:
                return await _one(http, company, since, args.describe)

        for lines in await asyncio.gather(*(run(c) for c in companies)):
            print("\n".join(lines), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
