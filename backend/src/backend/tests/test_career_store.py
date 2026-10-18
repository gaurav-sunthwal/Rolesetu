"""Saving collected jobs to the database, the collector's lease, and the
limits on what a user can ask the server to read."""

import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update

from backend.db.session import get_sessionmaker
from backend.main import app
from backend.modules.career_jobs import service, store
from backend.modules.career_jobs.collect import _stored
from backend.modules.career_jobs.detect import detect_source
from backend.modules.career_jobs.models import CareerCollector, CareerCompany
from backend.modules.career_jobs.sources.base import Posting
from backend.modules.career_jobs.store import StoredCompany, StoredJob

COMPANIES = "/api/v1/career-jobs/companies"


@pytest.fixture
async def slug() -> AsyncGenerator[str]:
    """A company of this test's own; it and its jobs are removed afterwards."""
    name = f"test-{uuid.uuid4().hex[:12]}"
    yield name
    async with get_sessionmaker()() as db:
        await db.execute(delete(CareerCompany).where(CareerCompany.slug.like(f"{name}%")))
        await db.commit()


@pytest.fixture
async def collector() -> AsyncGenerator[None]:
    """Puts the collector's row back as it was, since every server shares it."""
    async with get_sessionmaker()() as db:
        row = await db.scalar(select(CareerCollector).where(CareerCollector.id == 1))
        assert row is not None, "the migration creates the collector's row"
        saved = (row.lease_until, row.last_finished_at)
        await db.execute(
            update(CareerCollector).where(CareerCollector.id == 1).values(lease_until=None)
        )
        await db.commit()
    yield
    async with get_sessionmaker()() as db:
        await db.execute(
            update(CareerCollector)
            .where(CareerCollector.id == 1)
            .values(lease_until=saved[0], last_finished_at=saved[1])
        )
        await db.commit()


def company(slug: str, **changes: object) -> StoredCompany:
    return StoredCompany(
        slug=slug, name="Test Co", kind="lever", config={"token": slug}
    ).model_copy(update=changes)


def job(slug: str, number: int, *, seen: date | None = None) -> StoredJob:
    return StoredJob(
        id=f"{slug}:{number}",
        company_slug=slug,
        title=f"Engineer {number}",
        url=f"https://example.com/{slug}/{number}",
        location="Pune",
        places=["Pune"],
        posted_on=None,
        first_seen=seen or date.today(),
        description="We need Python.",
        min_years=1,
        max_years=None,
        experience_source="stated",
        experience_quote="1+ years",
    )


async def test_a_company_read_replaces_its_jobs_and_a_failed_read_keeps_them(slug: str) -> None:
    sessions = get_sessionmaker()
    async with sessions() as db:
        before = await store.version(db)
        await store.save_company(db, company(slug), [job(slug, 1), job(slug, 2)])
        await db.commit()
    async with sessions() as db:
        assert {j.id for j in await store.jobs_of(db, [slug])} == {f"{slug}:1", f"{slug}:2"}
        assert await store.version(db) > before

        # The next read found only job 3: the others are gone.
        await store.save_company(db, company(slug), [job(slug, 3)])
        await db.commit()
    async with sessions() as db:
        assert [j.id for j in await store.jobs_of(db, [slug])] == [f"{slug}:3"]

        # A failed read records why, and keeps what the company had.
        await store.save_company(db, company(slug, error="TimeoutError: slow"), None)
        await db.commit()
    async with sessions() as db:
        assert [j.id for j in await store.jobs_of(db, [slug])] == [f"{slug}:3"]
        saved = {c.slug: c for c in await store.companies(db)}[slug]
        assert saved.error == "TimeoutError: slow"


async def test_the_whole_collection_is_reread_only_when_it_changed(slug: str) -> None:
    sessions = get_sessionmaker()
    async with sessions() as db:
        first = await store.current(db)
        assert await store.current(db) is first  # unchanged: the copy held is used
        await store.save_company(db, company(slug), [job(slug, 1)])
        await db.commit()
    async with sessions() as db:
        changed = await store.current(db)
        assert changed is not first and f"{slug}:1" in {j.id for j in changed.jobs}


async def test_old_jobs_are_dropped(slug: str) -> None:
    sessions = get_sessionmaker()
    week_ago = date.today() - timedelta(days=store.KEEP_DAYS + 1)
    async with sessions() as db:
        await store.save_company(db, company(slug), [job(slug, 1), job(slug, 2, seen=week_ago)])
        await store.prune(db, date.today() - timedelta(days=store.KEEP_DAYS))
        await db.commit()
    async with sessions() as db:
        assert [j.id for j in await store.jobs_of(db, [slug])] == [f"{slug}:1"]


@pytest.mark.usefixtures("collector")
async def test_only_one_server_collects_at_a_time() -> None:
    sessions = get_sessionmaker()
    async with sessions() as db:
        assert await store.take_lease(db, timedelta(minutes=5))
        await db.commit()
    async with sessions() as db:
        # Another server checking now finds it taken.
        assert not await store.take_lease(db, timedelta(minutes=5))
        await store.release(db)
        await db.commit()
    async with sessions() as db:
        assert await store.take_lease(db, timedelta(minutes=5))
        await db.commit()


@pytest.mark.usefixtures("collector")
async def test_a_collection_is_due_once_a_day() -> None:
    sessions = get_sessionmaker()
    async with sessions() as db:
        await store.finish(db)
        await db.commit()
    async with sessions() as db:
        assert not await store.is_due(db, timedelta(hours=20))
        assert await store.is_due(db, timedelta(seconds=0))


async def test_following_companies_needs_sign_in() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        for response in (
            await anonymous.get(COMPANIES),
            await anonymous.post(COMPANIES, json={"link": "https://jobs.lever.co/acme"}),
            await anonymous.get("/api/v1/career-jobs"),
        ):
            assert response.status_code == 401


async def test_one_user_cannot_add_many_sites_a_day(
    client: AsyncClient, slug: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])
    async with get_sessionmaker()() as db:
        for number in range(service.MAX_ADDS_PER_DAY):
            await store.save_company(
                db, company(f"{slug}-{number}", added=True), [], added_by=user_id
            )
        await db.commit()

    async def never_called(*_: object, **__: object) -> None:
        raise AssertionError("the site must not be read once the limit is reached")

    monkeypatch.setattr(service, "collect", never_called)
    response = await client.post(COMPANIES, json={"link": f"https://jobs.lever.co/{slug}-new"})
    assert response.status_code == 429


@pytest.mark.parametrize(
    "link",
    [
        "https://boards.greenhouse.io/..%2F..%2Fadmin",
        "https://jobs.lever.co/acme.example",
        "https://acme.wd1.myworkdayjobs.com/%2E%2E",
        "https://evil.example/jobs.lever.co/acme",
    ],
)
def test_careers_links_with_odd_names_are_refused(link: str) -> None:
    assert detect_source(link) is None


def test_a_job_link_that_is_not_a_web_address_is_not_kept() -> None:
    posting = Posting(
        source_id="1",
        title="Engineer",
        url="javascript:alert(1)",
        location="Pune",
        posted_on=None,
        description="We need Python.",
    )
    assert _stored(company("acme"), posting, date.today()) is None
