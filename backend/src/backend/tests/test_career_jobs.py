"""Which collected jobs a user sees: the experience rule, filters and paging.

The profile and the collection are passed in directly, so nothing here
touches the database; test_career_store.py covers saving them.
"""

import asyncio
import time
import uuid
from datetime import UTC, date, datetime

import pytest

from backend.core.exceptions import ValidationFailedError
from backend.modules.career_jobs import service, store
from backend.modules.career_jobs.fit import fit_for
from backend.modules.career_jobs.repository import same_job
from backend.modules.career_jobs.schemas import CareerJobPage
from backend.modules.career_jobs.store import Collection, StoredCompany, StoredJob
from backend.modules.career_jobs.work_mode import WorkMode
from backend.modules.profiles.schemas import ProfileRead


@pytest.mark.parametrize(
    ("have", "min_years", "max_years", "source", "kind"),
    [
        # Asks for no more than the user has.
        (3, 2, 4, "stated", "fits"),
        (0, 0, None, "fresher", "fits"),
        # Up to one year more: shown, labelled a stretch.
        (1, 1.5, 2, "stated", "stretch"),
        (1, 2, None, "stated", "stretch"),
        (0, 1, None, "stated", "stretch"),
        # More than one year more: not shown.
        (1, 2.5, None, "stated", None),
        (1, 5, None, "title", None),
        # Far below the user's level: not shown.
        (6, 0, None, "fresher", None),
        (8, 2, 4, "stated", None),
        # No number in the posting: shown, and said so.
        (2, None, None, None, "not_stated"),
    ],
)
def test_experience_rule(
    have: float, min_years: float | None, max_years: float | None, source: str | None, kind: str
) -> None:
    fit = fit_for(have, min_years=min_years, max_years=max_years, source=source)
    assert (fit.kind if fit else None) == kind


def test_a_stretch_says_so() -> None:
    fit = fit_for(1, min_years=2, max_years=None, source="stated")
    assert fit is not None
    assert "stretch" in fit.note.lower()
    assert "2 years+" in fit.note


def _profile(years: int) -> ProfileRead:
    start = f"{date.today().year - years}-{date.today().month:02d}"
    return ProfileRead.model_validate(
        {
            "full_name": "Test User",
            "headline": None,
            "location": None,
            "phone": None,
            "links": {},
            "skills": [{"id": "s1", "name": "Python"}, {"id": "s2", "name": "React"}],
            "experience": [
                {"id": "e1", "title": "Engineer", "company": "Acme", "start": start, "end": None}
            ]
            if years
            else [],
            "projects": [],
            "education": [],
            "version": 1,
            "completeness": 80,
            "updated_at": None,
        }
    )


def _job(slug: str, number: int, *, min_years: float | None, place: str) -> StoredJob:
    return StoredJob(
        id=f"{slug}:{number}",
        company_slug=slug,
        title=f"Engineer {number}",
        url=f"https://example.com/{slug}/{number}",
        location=place,
        places=[place],
        posted_on=date.today(),
        first_seen=date.today(),
        description="We need Python and React. Experience with Kubernetes is required.",
        min_years=min_years,
        max_years=None,
        experience_source="stated" if min_years is not None else None,
        experience_quote=None,
    )


class FakeStore:
    """Stands in for the database copy of the collection."""

    def __init__(self) -> None:
        self.collection = Collection()

    def set(self, companies: list[StoredCompany], jobs: list[StoredJob]) -> None:
        self.collection = Collection(
            version=self.collection.version + 1,
            collected_at=datetime.now(UTC),
            companies=companies,
            jobs=jobs,
        )

    async def current(self, _db: object) -> Collection:
        return self.collection

    async def companies(self, _db: object) -> list[StoredCompany]:
        return self.collection.companies

    async def job_counts(self, _db: object) -> dict[str, int]:
        counts: dict[str, int] = {}
        for job in self.collection.jobs:
            counts[job.company_slug] = counts.get(job.company_slug, 0) + 1
        return counts


@pytest.fixture
def collection(monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    fake = FakeStore()
    for name in ("current", "companies", "job_counts"):
        monkeypatch.setattr(store, name, getattr(fake, name))
    service._cache.clear()
    service._previous.clear()
    service._runs.clear()
    companies = [
        StoredCompany(slug="acme", name="Acme", kind="lever", config={"token": "acme"}),
        StoredCompany(slug="globex", name="Globex", kind="lever", config={"token": "globex"}),
    ]
    jobs = [
        _job("acme", 1, min_years=1, place="Pune"),
        _job("acme", 2, min_years=2, place="Bengaluru"),  # a stretch for 1 year
        _job("acme", 3, min_years=4, place="Pune"),  # too senior
        _job("globex", 4, min_years=None, place="Bengaluru"),
        _job("globex", 5, min_years=0, place="Hyderabad"),
    ]
    fake.set(companies, jobs)
    return fake


async def _list(
    monkeypatch: pytest.MonkeyPatch,
    *,
    years: int = 1,
    companies: list[str] | None = None,
    places: list[str] | None = None,
    work_modes: list[WorkMode] | None = None,
    include_stretch: bool = True,
    cursor: str | None = None,
    limit: int = 20,
    tracked: set[str] | None = None,
    user_id: uuid.UUID | None = None,
    wait: bool = True,
) -> CareerJobPage:
    tracked = tracked or set()
    profile = _profile(years)
    user_id = user_id or uuid.uuid4()

    async def fake_profile(_db: object, *, user_id: uuid.UUID) -> ProfileRead:
        return profile

    async def fake_tracked(_db: object, _user_id: uuid.UUID) -> set[str]:
        return tracked

    monkeypatch.setattr(service, "get_profile", fake_profile)
    monkeypatch.setattr(service, "tracked_urls", fake_tracked)

    async def once() -> CareerJobPage:
        return await service.list_jobs(
            None,  # type: ignore[arg-type]  # the profile lookup above never uses it
            user_id=user_id,
            companies=companies or [],
            places=places or [],
            work_modes=work_modes or [],
            include_stretch=include_stretch,
            cursor=cursor,
            limit=limit,
        )

    page = await once()
    if not wait:
        return page
    for _ in range(200):
        if page.scored_percent == 100 and not page.refreshing:
            return page
        await asyncio.sleep(0.01)
        page = await once()
    raise AssertionError("scoring did not finish")


@pytest.mark.usefixtures("collection")
async def test_scored_jobs_show_before_the_run_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    real = service._score

    def slow(
        profile: ProfileRead, job: StoredJob, candidate_years: float
    ) -> service.CareerJobRead | None:
        time.sleep(0.05)
        return real(profile, job, candidate_years)

    monkeypatch.setattr(service, "_score", slow)
    started = await _list(monkeypatch, user_id=user_id, wait=False)
    assert started.refreshing
    assert started.items == []
    midway: CareerJobPage | None = None
    for _ in range(40):
        await asyncio.sleep(0.02)
        page = await _list(monkeypatch, user_id=user_id, wait=False)
        if page.items and page.refreshing and page.scored_percent < 100:
            midway = page
            break
    assert midway is not None
    done = await _list(monkeypatch, user_id=user_id)
    assert done.scored_percent == 100
    assert len(done.items) >= len(midway.items)


@pytest.mark.usefixtures("collection")
async def test_an_older_list_stays_up_while_new_jobs_are_scored(
    monkeypatch: pytest.MonkeyPatch, collection: FakeStore
) -> None:
    user_id = uuid.uuid4()
    first = await _list(monkeypatch, user_id=user_id)
    assert first.scored_percent == 100
    real = service._score

    def slow(
        profile: ProfileRead, job: StoredJob, candidate_years: float
    ) -> service.CareerJobRead | None:
        time.sleep(0.05)
        return real(profile, job, candidate_years)

    monkeypatch.setattr(service, "_score", slow)
    collection.set(
        collection.collection.companies,
        [*collection.collection.jobs, _job("acme", 9, min_years=1, place="Pune")],
    )
    early = await _list(monkeypatch, user_id=user_id, wait=False)
    assert early.refreshing
    assert early.scored_percent < 100
    assert {job.id for job in early.items} == {job.id for job in first.items}
    done = await _list(monkeypatch, user_id=user_id)
    assert done.scored_percent == 100
    assert "acme:9" in {job.id for job in done.items}


@pytest.mark.usefixtures("collection")
async def test_jobs_are_picked_by_experience(monkeypatch: pytest.MonkeyPatch) -> None:
    page = await _list(monkeypatch, years=1)
    by_id = {job.id: job for job in page.items}
    assert set(by_id) == {"acme:1", "acme:2", "globex:4", "globex:5"}
    assert by_id["acme:2"].fit == "stretch"
    assert by_id["globex:4"].fit == "not_stated"
    assert by_id["acme:1"].company == "Acme"
    # Every shown score comes with the skills behind it.
    assert all(job.skill_results for job in page.items)
    # The current month counts too, so a year-old role reads as 1.1.
    assert page.candidate_years == pytest.approx(1, abs=0.2)


@pytest.mark.usefixtures("collection")
async def test_stretch_roles_can_be_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    page = await _list(monkeypatch, include_stretch=False)
    assert "acme:2" not in {job.id for job in page.items}


@pytest.mark.usefixtures("collection")
async def test_filters_by_company_and_city(monkeypatch: pytest.MonkeyPatch) -> None:
    page = await _list(monkeypatch, companies=["acme"], places=["Pune"])
    assert [job.id for job in page.items] == ["acme:1"]
    # The city list counts every city of the chosen companies, not only the chosen city.
    assert {p.name: p.count for p in page.places} == {"Pune": 1, "Bengaluru": 1}


@pytest.mark.usefixtures("collection")
async def test_pages_through_every_job_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    cursor: str | None = None
    while True:
        page = await _list(monkeypatch, cursor=cursor, limit=3)
        seen += [job.id for job in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert sorted(seen) == ["acme:1", "acme:2", "globex:4", "globex:5"]
    assert page.total == 4


async def test_a_score_on_little_evidence_ranks_after_real_ones(
    monkeypatch: pytest.MonkeyPatch, collection: FakeStore
) -> None:
    thin = _job("acme", 6, min_years=1, place="Pune").model_copy(
        update={"description": "You will write Python."}
    )
    rich = _job("acme", 7, min_years=1, place="Pune").model_copy(
        update={"description": "Python, React, Kubernetes, Docker and AWS are required."}
    )
    collection.set(collection.collection.companies, [thin, rich])
    page = await _list(monkeypatch)
    by_id = {job.id: job for job in page.items}
    # The single-skill job scores higher, yet the well-evidenced one comes first.
    assert (by_id["acme:6"].score or 0) > (by_id["acme:7"].score or 0)
    assert [job.id for job in page.items] == ["acme:7", "acme:6"]


async def test_adding_a_company_already_followed_returns_it(collection: FakeStore) -> None:
    # Zeta is in the catalog as "zeta"; its Lever link must not add it twice.
    company = await service.add_company(
        None,  # type: ignore[arg-type]
        "https://jobs.lever.co/zeta",
        user_id=uuid.uuid4(),
    )
    assert company.slug == "zeta"
    assert all(j.company_slug != "lever-zeta" for j in collection.collection.jobs)


@pytest.mark.usefixtures("collection")
async def test_unknown_careers_sites_are_refused_plainly() -> None:
    with pytest.raises(ValidationFailedError, match="can't read that careers site"):
        await service.add_company(
            None,  # type: ignore[arg-type]
            "https://www.accenture.com/in-en/careers",
            user_id=uuid.uuid4(),
        )


@pytest.mark.usefixtures("collection")
async def test_a_job_already_applied_to_is_not_shown_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tracked as "https://example.com/acme/1/" from the Applications page: same job.
    page = await _list(monkeypatch, tracked={same_job("HTTPS://example.com/acme/1/")})
    assert "acme:1" not in {job.id for job in page.items}
    assert page.total == 3


async def test_filters_by_work_mode(monkeypatch: pytest.MonkeyPatch, collection: FakeStore) -> None:
    remote = _job("acme", 8, min_years=1, place="Remote")
    hybrid = _job("acme", 9, min_years=1, place="Pune").model_copy(
        update={"description": "Python and React. This role follows our hybrid work model."}
    )
    unsaid = _job("acme", 10, min_years=1, place="Pune")
    collection.set(collection.collection.companies, [remote, hybrid, unsaid])

    page = await _list(monkeypatch)
    assert {job.id: job.work_mode for job in page.items} == {
        "acme:8": "remote",
        "acme:9": "hybrid",
        "acme:10": "not_stated",
    }
    assert {m.mode: m.count for m in page.work_modes} == {
        "remote": 1,
        "hybrid": 1,
        "not_stated": 1,
    }
    # Remote has its own filter now, so the city list leaves it out.
    assert {p.name for p in page.places} == {"Pune"}

    page = await _list(monkeypatch, work_modes=["remote", "hybrid"])
    assert sorted(job.id for job in page.items) == ["acme:8", "acme:9"]


@pytest.mark.usefixtures("collection")
async def test_each_job_says_which_skills_would_raise_its_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = await _list(monkeypatch)
    job = next(job for job in page.items if job.id == "acme:1")
    missing = {s.name for s in job.skill_results if s.verdict != "strong"}
    assert missing, "the posting asks for Kubernetes, which the profile lacks"
    assert {boost.name for boost in job.score_boosts} == missing
    points = [boost.points for boost in job.score_boosts]
    assert points == sorted(points, reverse=True)
    assert all(boost.points > 0 for boost in job.score_boosts)
