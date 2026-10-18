"""Companies with their own job search rather than a hiring platform."""

import asyncio
import json
import re
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

MAX_PAGES = 100


class Amazon(ListOnly):
    PAGE = 100

    async def recent(self, http: Http, since: date) -> list[Posting]:
        found: list[Posting] = []
        for page in range(MAX_PAGES):
            params = {
                "country": "IND",
                "sort": "recent",
                "result_limit": self.PAGE,
                "offset": page * self.PAGE,
            }
            data = await http.get_json("https://www.amazon.jobs/en/search.json", params)
            jobs = (data or {}).get("jobs")
            if not isinstance(jobs, list):
                raise SourceError("amazon.jobs: unexpected job list")
            if not jobs:
                break
            for job in jobs:
                posted = datetime.strptime(job["posted_date"], "%B %d, %Y").date()
                if posted < since:
                    return found
                markup = (
                    f"{job.get('description') or ''}"
                    f"<h3>Basic qualifications</h3>{job.get('basic_qualifications') or ''}"
                    f"<h3>Preferred qualifications</h3>{job.get('preferred_qualifications') or ''}"
                )
                found.append(
                    Posting(
                        source_id=str(job["id_icims"]),
                        title=job.get("title", "").strip(),
                        url=f"https://www.amazon.jobs{job.get('job_path', '')}",
                        location=job.get("location") or job.get("city") or "",
                        posted_on=posted,
                        description=to_text(markup),
                    )
                )
        return found


class IBM(ListOnly):
    PAGE = 100

    async def recent(self, http: Http, since: date) -> list[Posting]:
        found: list[Posting] = []
        for page in range(MAX_PAGES):
            body = {
                "appId": "careers",
                "scopes": ["careers2"],
                "query": {"bool": {"must": []}},
                "post_filter": {"term": {"field_keyword_05": "India"}},
                "from": page * self.PAGE,
                "size": self.PAGE,
                "sort": [{"dcdate": "desc"}],
                "_source": ["url", "dcdate", "title", "body", "field_keyword_19", "field_text_01"],
            }
            data = await http.post_json("https://www-api.ibm.com/search/api/v2", body)
            try:
                hits = data["hits"]["hits"]
            except (KeyError, TypeError) as exc:
                raise SourceError("ibm.com: unexpected job list") from exc
            if not hits:
                break
            for hit in hits:
                job = hit["_source"]
                posted = date.fromisoformat(job["dcdate"]) if job.get("dcdate") else None
                if posted is not None and posted < since:
                    return found
                found.append(
                    Posting(
                        source_id=str(job.get("field_text_01") or hit["_id"]),
                        title=job.get("title", "").strip(),
                        url=job.get("url", ""),
                        location=job.get("field_keyword_19") or "India",
                        posted_on=posted,
                        description=(job.get("body") or "").strip() or None,
                    )
                )
        return found


class Capgemini(ListOnly):
    PAGE = 100
    API = "https://cg-jobstream-api.azurewebsites.net/api/job-search"

    async def _page(self, http: Http, page: int) -> dict[str, Any]:
        params = {"country_code": "in-en", "page": page, "size": self.PAGE}
        data = await http.get_json(self.API, params)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise SourceError("capgemini: unexpected job list")
        return data

    async def recent(self, http: Http, since: date) -> list[Posting]:
        first = await self._page(http, 1)
        pages = range(2, int(first.get("count") or 0) // self.PAGE + 2)
        rest = await asyncio.gather(*(self._page(http, page) for page in pages))
        found: dict[str, Posting] = {}
        for result in (first, *rest):
            for job in result["data"]:
                # When the job first reached the search; updated_at moves on every edit.
                stamp = job.get("indexed_at") or job.get("updated_at")
                posted = date.fromisoformat(stamp[:10]) if stamp else None
                if posted is not None and posted < since:
                    continue
                key = str(job.get("ref") or job["id"])
                found[key] = Posting(
                    source_id=key,
                    title=job.get("title", "").strip(),
                    url=job.get("apply_job_url") or "",
                    location=job.get("location") or "India",
                    posted_on=posted,
                    description=to_text(job.get("description")) or job.get("description_stripped"),
                )
        return list(found.values())


class Google(ListOnly):
    """Google's careers page carries its results as data in the page itself."""

    URL = "https://www.google.com/about/careers/applications/jobs/results/"
    _DATA = re.compile(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", re.S)

    async def recent(self, http: Http, since: date) -> list[Posting]:
        found: list[Posting] = []
        for page in range(1, MAX_PAGES):
            params = {"location": "India", "sort_by": "date", "page": page}
            markup = await http.get_text(self.URL, params)
            match = self._DATA.search(markup)
            try:
                jobs = json.loads(match.group(1))[0] if match else None
            except (ValueError, IndexError) as exc:
                raise SourceError("google careers: unexpected page data") from exc
            if jobs is None:
                raise SourceError("google careers: no job data in the page")
            if not jobs:
                break
            for job in jobs:
                # The list is in order of last update (13); 12 is when it was first posted.
                updated = from_timestamp(job[13][0]) if job[13] else None
                if updated is not None and updated < since:
                    return found
                posted = from_timestamp(job[12][0]) if job[12] else updated
                if posted is not None and posted < since:
                    continue
                sections = [job[10], job[3], job[4]]
                markup = "".join(s[1] for s in sections if isinstance(s, list) and len(s) > 1)
                found.append(
                    Posting(
                        source_id=str(job[0]),
                        title=str(job[1]).strip(),
                        url=f"{self.URL}{job[0]}",
                        location="; ".join(place[0] for place in job[9] or []),
                        posted_on=posted,
                        description=to_text(markup),
                    )
                )
        return found


class Atlassian(ListOnly):
    """One list of every open job, without dates."""

    async def recent(self, http: Http, since: date) -> list[Posting]:
        data = await http.get_json("https://www.atlassian.com/endpoint/careers/listings")
        if not isinstance(data, list):
            raise SourceError("atlassian: unexpected job list")
        found = []
        for job in data:
            location = "; ".join(job.get("locations") or [])
            if not is_india(location):
                continue
            markup = "".join(
                job.get(part) or "" for part in ("overview", "responsibilities", "qualifications")
            )
            found.append(
                Posting(
                    source_id=str(job["id"]),
                    title=job.get("title", "").strip(),
                    url=(job.get("portalJobPost") or {}).get("portalUrl")
                    or job.get("applyUrl", ""),
                    location=location,
                    posted_on=None,
                    description=to_text(markup),
                )
            )
        return found
