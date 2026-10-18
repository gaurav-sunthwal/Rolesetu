"""Enterprise hiring platforms that list newest first: Eightfold (Microsoft),
SAP SuccessFactors (Wipro) and Oracle Recruiting Cloud (Oracle). Each is read
page by page until the jobs are older than the window.
"""

import re
from datetime import date, datetime
from typing import Any

from backend.modules.career_jobs.sources.base import Http, Posting, SourceError, from_timestamp

# A careless site could page forever; nobody posts this many in a week.
MAX_PAGES = 200


class Eightfold:
    def __init__(self, host: str, domain: str) -> None:
        self.host, self.domain = host, domain

    async def recent(self, http: Http, since: date) -> list[Posting]:
        found: list[Posting] = []
        start = 0
        for _ in range(MAX_PAGES):
            params = {
                "domain": self.domain,
                "query": "",
                "location": "India",
                "start": start,
                "sort_by": "timestamp",
            }
            data = await http.get_json(f"https://{self.host}/api/pcsx/search", params)
            positions = ((data or {}).get("data") or {}).get("positions")
            if not isinstance(positions, list):
                raise SourceError(f"{self.host}: unexpected job list")
            if not positions:
                break
            for job in positions:
                posted = from_timestamp(job["postedTs"]) if job.get("postedTs") else None
                if posted is not None and posted < since:
                    return found
                found.append(
                    Posting(
                        source_id=str(job["id"]),
                        title=job.get("name", "").strip(),
                        url=f"https://{self.host}/careers/job/{job['id']}",
                        location="; ".join(job.get("locations") or []),
                        posted_on=posted,
                    )
                )
            start += len(positions)
        return found

    async def complete(self, http: Http, posting: Posting) -> Posting | None:
        params = {"position_id": posting.source_id, "domain": self.domain, "hl": "en"}
        data = await http.get_json(f"https://{self.host}/api/pcsx/position_details", params)
        details = (data or {}).get("data") or {}
        return posting.with_description(details.get("jobDescription"))


class SuccessFactors:
    """Career sites built on SuccessFactors' Career Site Builder."""

    def __init__(self, host: str) -> None:
        self.host = host

    async def recent(self, http: Http, since: date) -> list[Posting]:
        found: list[Posting] = []
        for page in range(MAX_PAGES):
            body = {
                "locale": "en_US",
                "pageNumber": page,
                "sortBy": "date",
                "keywords": "",
                "location": "India",
                "facetFilters": {},
                "brand": "",
                "skills": [],
                "categoryId": 0,
                "alertId": "",
                "rcmCandidateId": "",
            }
            data = await http.post_json(f"https://{self.host}/services/recruiting/v1/jobs", body)
            results = (data or {}).get("jobSearchResult")
            if not isinstance(results, list):
                raise SourceError(f"{self.host}: unexpected job list")
            if not results:
                break
            for result in results:
                job = result.get("response") or {}
                started = job.get("unifiedStandardStart")
                posted = datetime.strptime(started, "%m/%d/%y").date() if started else None
                if posted is not None and posted < since:
                    return found
                places = [re.sub(r"<[^>]+>", "", p) for p in job.get("jobLocationShort") or []]
                slug = job.get("urlTitle") or "job"
                found.append(
                    Posting(
                        source_id=str(job["id"]),
                        title=(job.get("unifiedStandardTitle") or "").strip(),
                        url=f"https://{self.host}/job/{slug}/{job['id']}-en_US",
                        location="; ".join(places),
                        posted_on=posted,
                    )
                )
        return found

    async def complete(self, http: Http, posting: Posting) -> Posting | None:
        # The job page is drawn by JavaScript; the RSS feed, searched by id, has the text.
        params = {"locale": "en_US", "keywords": f"({posting.source_id})"}
        feed = await http.get_text(f"https://{self.host}/services/rss/job/", params)
        item = re.search(r"<item>.*?<description><!\[CDATA\[(.*?)\]\]></description>", feed, re.S)
        return posting.with_description(item.group(1) if item else None)


class OracleRecruiting:
    PAGE = 25

    def __init__(self, host: str, site: str, job_url: str) -> None:
        self.host, self.site, self.job_url = host, site, job_url
        self.base = f"https://{host}/hcmRestApi/resources/latest"

    async def recent(self, http: Http, since: date) -> list[Posting]:
        found: list[Posting] = []
        for page in range(MAX_PAGES):
            finder = (
                f"findReqs;siteNumber={self.site},limit={self.PAGE},offset={page * self.PAGE},"
                "location=India,sortBy=POSTING_DATES_DESC"
            )
            params = {"onlyData": "true", "expand": "requisitionList", "finder": finder}
            data = await http.get_json(f"{self.base}/recruitingCEJobRequisitions", params)
            try:
                jobs = data["items"][0]["requisitionList"]
            except (KeyError, IndexError, TypeError) as exc:
                raise SourceError(f"{self.host}: unexpected job list") from exc
            if not jobs:
                break
            for job in jobs:
                posted = date.fromisoformat(job["PostedDate"]) if job.get("PostedDate") else None
                if posted is not None and posted < since:
                    return found
                found.append(
                    Posting(
                        source_id=str(job["Id"]),
                        title=(job.get("Title") or "").strip(),
                        url=self.job_url.format(id=job["Id"]),
                        location=job.get("PrimaryLocation") or "",
                        posted_on=posted,
                    )
                )
        return found

    async def complete(self, http: Http, posting: Posting) -> Posting | None:
        params = {
            "onlyData": "true",
            "expand": "all",
            "finder": f'ById;Id="{posting.source_id}",siteNumber={self.site}',
        }
        data = await http.get_json(f"{self.base}/recruitingCEJobRequisitionDetails", params)
        items: list[dict[str, Any]] = (data or {}).get("items") or [{}]
        job = items[0]
        markup = "".join(
            job.get(field) or ""
            for field in (
                "ExternalDescriptionStr",
                "ExternalResponsibilitiesStr",
                "ExternalQualificationsStr",
            )
        )
        return posting.with_description(markup)
