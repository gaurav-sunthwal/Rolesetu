"""Job-board platforms with a public API per company: Greenhouse, Lever,
Ashby and SmartRecruiters. Startups and product companies mostly use these.
"""

import asyncio
import html
from datetime import date, datetime
from typing import Any

from backend.modules.career_jobs.places import is_india
from backend.modules.career_jobs.sources.base import (
    Http,
    ListOnly,
    Posting,
    SourceError,
    from_timestamp,
    to_text,
)


def _day(stamp: str | None) -> date | None:
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()


def _keep(posting: Posting, since: date) -> bool:
    fresh = posting.posted_on is None or posting.posted_on >= since
    return fresh and is_india(posting.location)


class Greenhouse(ListOnly):
    def __init__(self, token: str) -> None:
        self.token = token

    async def recent(self, http: Http, since: date) -> list[Posting]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.token}/jobs"
        data = await http.get_json(url, {"content": "true"})
        jobs: list[dict[str, Any]] = (data or {}).get("jobs", [])
        postings = [
            Posting(
                source_id=str(job["id"]),
                title=job.get("title", "").strip(),
                url=job.get("absolute_url", ""),
                location=(job.get("location") or {}).get("name", ""),
                posted_on=_day(job.get("first_published") or job.get("updated_at")),
                # Greenhouse escapes the markup once more than it needs to.
                description=to_text(html.unescape(job.get("content") or "")),
            )
            for job in jobs
        ]
        return [p for p in postings if _keep(p, since)]


class Lever(ListOnly):
    def __init__(self, token: str) -> None:
        self.token = token

    async def recent(self, http: Http, since: date) -> list[Posting]:
        data = await http.get_json(
            f"https://api.lever.co/v0/postings/{self.token}", {"mode": "json"}
        )
        if not isinstance(data, list):
            raise SourceError(f"lever {self.token}: unexpected job list")
        postings = []
        for job in data:
            categories = job.get("categories") or {}
            places = categories.get("allLocations") or [categories.get("location") or ""]
            parts = [job.get("descriptionPlain") or ""]
            for section in job.get("lists") or []:
                parts += [section.get("text") or "", to_text(section.get("content")) or ""]
            parts.append(job.get("additionalPlain") or "")
            postings.append(
                Posting(
                    source_id=job["id"],
                    title=job.get("text", "").strip(),
                    url=job.get("hostedUrl", ""),
                    location=", ".join(places),
                    posted_on=from_timestamp(job["createdAt"] / 1000)
                    if job.get("createdAt")
                    else None,
                    description="\n".join(p for p in parts if p).strip() or None,
                )
            )
        return [p for p in postings if _keep(p, since)]


class Ashby(ListOnly):
    def __init__(self, token: str) -> None:
        self.token = token

    async def recent(self, http: Http, since: date) -> list[Posting]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.token}"
        data = await http.get_json(url)
        postings = []
        for job in (data or {}).get("jobs", []):
            if job.get("isListed") is False:
                continue
            places = [job.get("location") or ""] + [
                extra.get("location") or "" for extra in job.get("secondaryLocations") or []
            ]
            postings.append(
                Posting(
                    source_id=job["id"],
                    title=job.get("title", "").strip(),
                    url=job.get("jobUrl", ""),
                    location=", ".join(p for p in places if p),
                    posted_on=_day(job.get("publishedAt")),
                    description=job.get("descriptionPlain") or to_text(job.get("descriptionHtml")),
                )
            )
        return [p for p in postings if _keep(p, since)]


class SmartRecruiters:
    PAGE = 100

    def __init__(self, company: str) -> None:
        self.company = company
        self.base = f"https://api.smartrecruiters.com/v1/companies/{company}/postings"

    async def _page(self, http: Http, offset: int) -> dict[str, Any]:
        params = {"country": "in", "limit": self.PAGE, "offset": offset}
        data = await http.get_json(self.base, params)
        if not isinstance(data, dict) or "content" not in data:
            raise SourceError(f"smartrecruiters {self.company}: unexpected job list")
        return data

    async def recent(self, http: Http, since: date) -> list[Posting]:
        first = await self._page(http, 0)
        offsets = range(self.PAGE, int(first.get("totalFound") or 0), self.PAGE)
        rest = await asyncio.gather(*(self._page(http, o) for o in offsets))
        postings = []
        for page in (first, *rest):
            for job in page["content"]:
                place = job.get("location") or {}
                postings.append(
                    Posting(
                        source_id=job["id"],
                        title=job.get("name", "").strip(),
                        url=f"https://jobs.smartrecruiters.com/{self.company}/{job['id']}",
                        location=place.get("fullLocation")
                        or ", ".join(part for part in (place.get("city"), "India") if part),
                        posted_on=_day(job.get("releasedDate")),
                    )
                )
        return [p for p in postings if p.posted_on is None or p.posted_on >= since]

    async def complete(self, http: Http, posting: Posting) -> Posting | None:
        data = await http.get_json(f"{self.base}/{posting.source_id}")
        sections = ((data or {}).get("jobAd") or {}).get("sections") or {}
        markup = "".join(
            f"<h3>{part.get('title', '')}</h3>{part.get('text', '')}"
            for part in sections.values()
            if isinstance(part, dict)
        )
        return posting.with_description(markup)
