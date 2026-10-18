"""Reading jobs from careers sites: places, dates, Workday's filters, link
detection, and readers against recorded-shape responses (no network)."""

import json
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from backend.modules.career_jobs.detect import detect_source
from backend.modules.career_jobs.places import cities_in, is_india
from backend.modules.career_jobs.sources.base import Http, SourceError
from backend.modules.career_jobs.sources.boards import Greenhouse
from backend.modules.career_jobs.sources.workday import CAP, Workday, india_filter, posted_on

TODAY = date(2026, 10, 17)


@pytest.mark.parametrize(
    ("location", "cities"),
    [
        ("Bangalore, Karnataka, India", ["Bengaluru"]),
        ("IN, KA, Bengaluru", ["Bengaluru"]),
        ("Gurgaon; Pune; Bombay", ["Gurugram", "Pune", "Mumbai"]),
        ("Navi Mumbai, MH", ["Navi Mumbai"]),
        ("Remote - India", []),
    ],
)
def test_cities_are_filed_under_one_name(location: str, cities: list[str]) -> None:
    assert cities_in(location) == cities


@pytest.mark.parametrize(
    ("location", "india"),
    [
        ("Hyderabad - Phoenix Aquila, India", True),
        ("Gurugram, IND-06, IND, 122016", True),
        ("Kolkata", True),
        ("IN - Indianapolis", False),
        ("10202 E Washington St, Indianapolis,IN 46229-2670", False),
        ("Stockholm", False),
    ],
)
def test_india_is_told_apart_from_indiana(location: str, india: bool) -> None:
    assert is_india(location) is india


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("Posted Today", 0),
        ("Posted Yesterday", 1),
        ("Posted 3 Days Ago", 3),
        ("Posted 30+ Days Ago", 30),
    ],
)
def test_workday_posting_age(text: str, days: int) -> None:
    assert posted_on(text, TODAY) == TODAY - timedelta(days=days)


def test_workday_unknown_age_is_none() -> None:
    assert posted_on("Hiring now", TODAY) is None


def _facet(parameter: str, *values: tuple[str, str, int]) -> dict[str, Any]:
    return {
        "facetParameter": parameter,
        "values": [{"descriptor": d, "id": i, "count": c} for d, i, c in values],
    }


def test_india_filter_prefers_the_country_facet() -> None:
    facets = [
        {
            "facetParameter": "locationMainGroup",
            "values": [
                _facet("locationCountry", ("India", "in-id", 900), ("Sweden", "se", 3)),
                _facet("locations", ("India, Pune", "pune", 20)),
            ],
        }
    ]
    assert india_filter(facets) == {"locationCountry": ["in-id"]}


def test_india_filter_falls_back_to_indian_cities() -> None:
    facets = [
        _facet(
            "locations",
            ("Bangalore, India", "blr", 5),
            ("IN - Indianapolis", "indy", 2),
            ("Gurgaon, India", "ggn", 1),
        )
    ]
    assert india_filter(facets) == {"locations": ["blr", "ggn"]}


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_workday_splits_a_search_workday_caps() -> None:
    """A search at the cap is split by a filter until each piece fits."""
    families = _facet("jobFamilyGroup", ("Engineering", "eng", 1500), ("Sales", "sales", 900))
    country = _facet("locationCountry", ("India", "in", CAP))

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        applied = body["appliedFacets"]
        if "jobFamilyGroup" not in applied:
            return httpx.Response(
                200, json={"total": CAP, "jobPostings": [], "facets": [country, families]}
            )
        family = applied["jobFamilyGroup"][0]
        job = {
            "title": f"{family} job",
            "externalPath": f"/job/Pune/{family}_R{family}",
            "locationsText": "Pune, India",
            "postedOn": "Posted Today",
        }
        old = {**job, "externalPath": f"/job/Pune/old_{family}", "postedOn": "Posted 30+ Days Ago"}
        page = [job, old] if body["offset"] == 0 else []
        return httpx.Response(200, json={"total": 2, "jobPostings": page, "facets": []})

    async with _client(handler) as client:
        reader = Workday("acme.wd1.myworkdayjobs.com", "acme", "Careers")
        postings = await reader.recent(Http(client), date.today() - timedelta(days=7))

    assert sorted(p.title for p in postings) == ["eng job", "sales job"]
    assert postings[0].url.startswith("https://acme.wd1.myworkdayjobs.com/en-US/Careers/job/")


async def test_greenhouse_keeps_recent_india_jobs_with_text() -> None:
    fresh = date.today().isoformat()
    jobs = [
        {
            "id": 1,
            "title": "Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
            "location": {"name": "Bengaluru, India"},
            "first_published": f"{fresh}T09:00:00Z",
            "content": "&lt;p&gt;Build APIs in Python.&lt;/p&gt;",
        },
        {
            "id": 2,
            "title": "Engineer, Berlin",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
            "location": {"name": "Berlin"},
            "first_published": f"{fresh}T09:00:00Z",
            "content": "",
        },
        {
            "id": 3,
            "title": "Old role",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/3",
            "location": {"name": "Pune"},
            "first_published": "2020-01-01T09:00:00Z",
            "content": "",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/boards/acme/jobs"
        return httpx.Response(200, json={"jobs": jobs})

    async with _client(handler) as client:
        postings = await Greenhouse("acme").recent(Http(client), date.today() - timedelta(days=7))

    assert [p.title for p in postings] == ["Backend Engineer"]
    assert postings[0].description == "Build APIs in Python."


@pytest.mark.parametrize(
    ("link", "kind", "config"),
    [
        (
            "https://acme.wd5.myworkdayjobs.com/en-US/External_Careers/job/x",
            "workday",
            {"host": "acme.wd5.myworkdayjobs.com", "tenant": "acme", "site": "External_Careers"},
        ),
        ("https://boards.greenhouse.io/razorpay", "greenhouse", {"token": "razorpay"}),
        ("https://job-boards.greenhouse.io/groww/jobs/123", "greenhouse", {"token": "groww"}),
        ("jobs.lever.co/cred", "lever", {"token": "cred"}),
        ("https://jobs.ashbyhq.com/sarvam", "ashby", {"token": "sarvam"}),
        ("https://jobs.smartrecruiters.com/Swiggy/1", "smartrecruiters", {"company": "Swiggy"}),
    ],
)
def test_careers_links_are_recognised(link: str, kind: str, config: dict[str, str]) -> None:
    detected = detect_source(link)
    assert detected is not None
    assert (detected.kind, detected.config) == (kind, config)


@pytest.mark.parametrize(
    "link", ["https://www.accenture.com/in-en/careers", "https://jobs.lever.co/", "not a link"]
)
def test_unknown_careers_links_are_not_guessed(link: str) -> None:
    assert detect_source(link) is None


async def test_a_maintenance_page_is_reported_as_such() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "acme.wd1.myworkdayjobs.com":
            return httpx.Response(
                303, headers={"location": "https://community.workday.com/maintenance-page"}
            )
        return httpx.Response(200, text="<html>We'll be back soon</html>")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        reader = Workday("acme.wd1.myworkdayjobs.com", "acme", "Careers")
        with pytest.raises(SourceError, match="down for maintenance"):
            await reader.recent(Http(client), date.today())
