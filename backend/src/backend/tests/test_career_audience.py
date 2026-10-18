"""Collecting only for the experience bands our users are in."""

import json
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from backend.modules.career_jobs.audience import EVERYONE, Audience, audience_from, band_of
from backend.modules.career_jobs.collect import read_company
from backend.modules.career_jobs.sources.base import Http
from backend.modules.career_jobs.sources.workday import Workday
from backend.modules.career_jobs.store import StoredCompany

# Today's users: 1 fresher, 3 junior, 2 mid. Nobody senior.
USERS = Audience({"fresher": 1, "junior": 3, "mid": 2})


@pytest.mark.parametrize(
    ("years", "band"),
    [(0, "fresher"), (0.9, "fresher"), (1, "junior"), (2.9, "junior"), (5.3, "mid"),
     (6, "senior"), (12, "very senior")],
)  # fmt: skip
def test_bands(years: float, band: str) -> None:
    assert band_of(years).name == band


@pytest.mark.parametrize(
    ("min_years", "source", "wanted"),
    [
        (0, "fresher", True),
        (2, "stated", True),
        (5, "stated", True),
        # One year above the top band: the mid users' stretch roles.
        (6.5, "stated", True),
        (7, "stated", False),
        (10, "stated", False),
        (5, "title", True),
        (7, "title", False),
        # No number: we cannot tell who it is for, so it is kept.
        (None, None, True),
    ],
)
def test_only_jobs_for_users_bands_are_wanted(
    min_years: float | None, source: str | None, wanted: bool
) -> None:
    assert USERS.wants(min_years=min_years, source=source) is wanted


def test_fresher_roles_are_skipped_when_no_one_is_a_fresher() -> None:
    seniors = Audience({"senior": 4})
    assert not seniors.wants(min_years=0, source="fresher")
    assert seniors.wants(min_years=8, source="stated")


def test_no_users_means_collect_everything() -> None:
    assert EVERYONE.wants(min_years=15, source="stated")


def test_audience_is_counted_from_profiles() -> None:
    today = date(2026, 10, 17)
    audience = audience_from(
        [
            [],
            [{"start": "2025-06", "end": None}],
            [{"start": "2018-01", "end": "2021-12"}, {"start": "2022-01", "end": None}],
        ],
        today,
    )
    assert audience.counts == {"fresher": 1, "junior": 1, "senior": 1}
    assert "Collecting for: fresher, junior, senior." in audience.describe()


async def test_senior_titles_are_never_read_in_full() -> None:
    """A title that rules a job out costs no request for its description."""
    fresh = date.today().isoformat()
    jobs = [
        {"id": 1, "title": "Backend Engineer", "absolute_url": "https://x/1",
         "location": {"name": "Pune, India"}, "first_published": f"{fresh}T09:00:00Z",
         "content": "&lt;p&gt;2+ years of Python.&lt;/p&gt;"},
        {"id": 2, "title": "Principal Architect", "absolute_url": "https://x/2",
         "location": {"name": "Pune, India"}, "first_published": f"{fresh}T09:00:00Z",
         "content": ""},
        {"id": 3, "title": "Platform Engineer", "absolute_url": "https://x/3",
         "location": {"name": "Pune, India"}, "first_published": f"{fresh}T09:00:00Z",
         "content": "&lt;p&gt;You bring 10+ years of experience in platform work.&lt;/p&gt;"},
    ]  # fmt: skip

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": jobs})

    company = StoredCompany(slug="acme", name="Acme", kind="greenhouse", config={"token": "acme"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await read_company(
            Http(client),
            company,
            since=date.today() - timedelta(days=7),
            known={},
            audience=USERS,
        )
    assert [job.title for job in result.jobs] == ["Backend Engineer"]
    # One ruled out by its title, one by its text.
    assert result.skipped == 2


def _facet(parameter: str, *values: tuple[str, str]) -> dict[str, Any]:
    return {
        "facetParameter": parameter,
        "values": [{"descriptor": d, "id": i, "count": 5} for d, i in values],
    }


async def test_workday_reads_only_the_chosen_job_families() -> None:
    facets = [
        _facet("locationCountry", ("India", "in")),
        _facet("jobFamilyGroup", ("Software Engineering", "swe"), ("Finance", "fin")),
    ]
    applied: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        applied.append(json.loads(request.content)["appliedFacets"])
        return httpx.Response(200, json={"total": 0, "jobPostings": [], "facets": facets})

    reader = Workday("acme.wd1.myworkdayjobs.com", "acme", "Careers", "Software Engineering")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await reader.recent(Http(client), date.today())
    assert applied[-1] == {"locationCountry": ["in"], "jobFamilyGroup": ["swe"]}
