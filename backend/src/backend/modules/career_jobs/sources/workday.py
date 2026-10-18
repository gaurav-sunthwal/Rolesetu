"""Workday careers sites (https://<company>.wdN.myworkdayjobs.com/<site>).

The list endpoint returns 20 jobs a page, in no useful order, and never more
than 2,000 for one search. A company with more open jobs than that in India
(Accenture has ~35,000) is read in slices: the search is split by one of its
own filters (job family, city, ...) until every slice fits.
"""

import asyncio
import re
from datetime import date, timedelta
from typing import Any

from backend.modules.career_jobs.places import is_india
from backend.modules.career_jobs.sources.base import Http, Posting, SourceError

PAGE = 20
CAP = 2000
_MAX_SPLITS = 3
# Filters that never narrow a search usefully.
_NOT_SPLITTABLE = {"distance", "timeType"}
_AGO = re.compile(r"(\d+)\+?\s+days?\s+ago", re.I)

Facets = dict[str, list[str]]


def posted_on(text: str | None, today: date) -> date | None:
    """Reads "Posted Today", "Posted Yesterday", "Posted 3 Days Ago", "Posted 30+ Days Ago"."""
    if not text:
        return None
    lowered = text.lower()
    if "today" in lowered:
        return today
    if "yesterday" in lowered:
        return today - timedelta(days=1)
    match = _AGO.search(lowered)
    return today - timedelta(days=int(match.group(1))) if match else None


def _flat(facets: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Every filter as (parameter, values). Workday nests some under a group
    ("locationMainGroup" holds "locationCountry" and "locations")."""
    found: list[tuple[str, list[dict[str, Any]]]] = []
    for facet in facets:
        values = facet.get("values") or []
        if values and all("facetParameter" in value for value in values):
            found.extend(_flat(values))
        else:
            found.append((facet.get("facetParameter", ""), values))
    return found


def india_filter(facets: list[dict[str, Any]]) -> Facets:
    """The search filter for jobs in India. Sites name it differently
    ("locationCountry", "Location_Country", "locationHierarchy1"); some only
    list cities, and then every Indian city is selected (values of one filter
    are OR'ed).
    """
    flat = _flat(facets)
    exact = [
        (parameter, value["id"])
        for parameter, values in flat
        for value in values
        if "id" in value and value.get("descriptor", "").strip().lower() == "india"
    ]
    if exact:
        parameter, value = next((e for e in exact if "country" in e[0].lower()), exact[0])
        return {parameter: [value]}
    for parameter, values in flat:
        if "location" not in parameter.lower():
            continue
        ids = [v["id"] for v in values if "id" in v and is_india(v.get("descriptor", ""))]
        if ids:
            return {parameter: ids}
    return {}


def _split(facets: list[dict[str, Any]], applied: Facets) -> tuple[str, list[str]] | None:
    """The filter that splits this search into the fewest pieces, so the fewest
    requests are made; a piece still too big is split again."""
    best: tuple[str, list[str]] | None = None
    for parameter, values in _flat(facets):
        if parameter in applied or parameter in _NOT_SPLITTABLE:
            continue
        ids = [value["id"] for value in values if value.get("count", 0) > 0 and "id" in value]
        if len(ids) > 1 and (best is None or len(ids) < len(best[1])):
            best = (parameter, ids)
    return best


class Workday:
    def __init__(self, host: str, tenant: str, site: str, families: str = "") -> None:
        """`families`: job families to read, comma separated, as the site names
        them. Empty reads every family."""
        self.host, self.site = host, site
        self.base = f"https://{host}/wday/cxs/{tenant}/{site}"
        self.families = {f.strip().lower() for f in families.split(",") if f.strip()}

    async def _page(self, http: Http, facets: Facets, offset: int) -> dict[str, Any]:
        body = {"appliedFacets": facets, "limit": PAGE, "offset": offset, "searchText": ""}
        data = await http.post_json(f"{self.base}/jobs", body)
        if not isinstance(data, dict) or "jobPostings" not in data:
            raise SourceError(f"{self.host}: unexpected job list")
        return data

    async def recent(self, http: Http, since: date) -> list[Posting]:
        today = date.today()
        first = await self._page(http, {}, 0)
        india = india_filter(first.get("facets", []))
        facets = india | self._family_filter(first.get("facets", []))
        found: dict[str, Posting] = {}
        await self._collect(http, facets, since, today, found, splits=0, checked_india=bool(india))
        return list(found.values())

    def _family_filter(self, facets: list[dict[str, Any]]) -> Facets:
        if not self.families:
            return {}
        for parameter, values in _flat(facets):
            if "family" not in parameter.lower():
                continue
            ids = [
                value["id"]
                for value in values
                if "id" in value and value.get("descriptor", "").strip().lower() in self.families
            ]
            if ids:
                return {parameter: ids}
        raise SourceError(f"{self.host}: none of the job families {sorted(self.families)} found")

    async def _collect(
        self,
        http: Http,
        facets: Facets,
        since: date,
        today: date,
        found: dict[str, Posting],
        *,
        splits: int,
        checked_india: bool,
    ) -> None:
        first = await self._page(http, facets, 0)
        total = int(first.get("total") or 0)
        # Workday reports a capped search as exactly CAP.
        if total >= CAP and splits < _MAX_SPLITS:
            split = _split(first.get("facets", []), facets)
            if split is not None:
                parameter, ids = split
                # Read side by side; Http still holds each site to a few requests at once.
                await asyncio.gather(
                    *(
                        self._collect(
                            http,
                            {**facets, parameter: [value]},
                            since,
                            today,
                            found,
                            splits=splits + 1,
                            checked_india=checked_india,
                        )
                        for value in ids
                    )
                )
                return
        offsets = range(PAGE, min(total, CAP), PAGE)
        rest = await asyncio.gather(*(self._page(http, facets, o) for o in offsets))
        for page in (first, *rest):
            for item in page["jobPostings"]:
                path = item.get("externalPath")
                if not path or path in found:
                    continue
                posted = posted_on(item.get("postedOn"), today)
                if posted is None or posted < since:
                    continue
                # Some sites leave locationsText out and put the city after the job id.
                bullets = [str(b) for b in item.get("bulletFields") or []][1:]
                location = item.get("locationsText") or ", ".join(bullets)
                # Without a country filter, "3 Locations" is settled when the job is read.
                many = "location" in location.lower()
                if not checked_india and not many and not is_india(location):
                    continue
                found[path] = Posting(
                    source_id=path.rsplit("_", 1)[-1],
                    title=item.get("title", "").strip(),
                    url=f"https://{self.host}/en-US/{self.site}{path}",
                    location=location,
                    posted_on=posted,
                )

    async def complete(self, http: Http, posting: Posting) -> Posting | None:
        path = posting.url.split(f"/{self.site}", 1)[1]
        data = await http.get_json(f"{self.base}{path}")
        info = (data or {}).get("jobPostingInfo")
        if not isinstance(info, dict):
            raise SourceError(f"{self.host}: unexpected job details")
        country = (info.get("country") or {}).get("descriptor", "")
        if country and country.strip().lower() != "india":
            return None
        locations = [info.get("location") or "", *(info.get("additionalLocations") or [])]
        started = info.get("startDate")
        complete = posting.with_description(info.get("jobDescription"))
        return Posting(
            source_id=complete.source_id,
            title=complete.title,
            url=info.get("externalUrl") or complete.url,
            location=", ".join(part for part in locations if part) or complete.location,
            posted_on=date.fromisoformat(started) if started else complete.posted_on,
            description=complete.description,
        )
