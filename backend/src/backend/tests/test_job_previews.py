"""The landing page's job preview: no sign-in, so it is limited by visitor instead."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.main import app
from backend.modules.previews import service as previews_service
from backend.modules.previews.models import JobPreview
from backend.modules.previews.service import _hash
from backend.tests.test_job_link import BLOCKED, POSTING, PROFILE, page_with, use_readers

PREVIEWS = "/api/v1/public/job-previews"


def job_url() -> str:
    return f"https://jobs.example.com/{uuid.uuid4()}"


@pytest.fixture
async def visitor() -> AsyncGenerator[AsyncClient]:
    """Someone who is not signed in, with an address of their own."""
    ip = f"203.0.113.{uuid.uuid4()}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"x-forwarded-for": ip}
    ) as client:
        yield client
    async with get_sessionmaker()() as db:
        await db.execute(delete(JobPreview).where(JobPreview.client_hash == _hash(ip)))
        await db.commit()


async def test_a_visitor_sees_what_the_job_asks_for_without_signing_in(
    visitor: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_readers(monkeypatch, page_with(POSTING))
    response = await visitor.post(PREVIEWS, json={"url": job_url()})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Full Stack AI Developer - Fresher (WFH)"
    assert body["company"] == "Megaminds IT Services"
    assert body["location"] == "Remote (Hyderabad, Telangana, IN)"
    assert {"React", "MySQL", "Python or Node.js or Flask"} <= set(body["required_skills"])
    assert "score" not in body


async def test_the_same_link_is_fetched_once_for_everyone(
    visitor: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = use_readers(monkeypatch, page_with(POSTING))
    url = job_url()
    first = await visitor.post(PREVIEWS, json={"url": url})
    again = await visitor.post(
        PREVIEWS, json={"url": url}, headers={"x-forwarded-for": "198.51.100.7"}
    )
    assert first.json() == again.json()
    assert readers.direct_calls == 1


async def test_a_visitor_is_limited_and_failed_links_count(
    visitor: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(previews_service, "MAX_PREVIEWS_PER_HOUR", 2)
    use_readers(monkeypatch, BLOCKED, None)
    for _ in range(2):
        assert (await visitor.post(PREVIEWS, json={"url": job_url()})).status_code == 422
    limited = await visitor.post(PREVIEWS, json={"url": job_url()})
    assert limited.status_code == 429
    assert "Sign in" in limited.json()["detail"]


async def test_previews_share_one_daily_budget_for_the_paid_reader(
    visitor: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = use_readers(monkeypatch, BLOCKED, page_with(POSTING))
    monkeypatch.setattr(get_settings(), "preview_rendered_reads_per_day", 0)
    assert (await visitor.post(PREVIEWS, json={"url": job_url()})).status_code == 422
    assert readers.rendered_calls == 0


async def test_signing_in_after_a_preview_does_not_fetch_the_page_again(
    visitor: AsyncClient, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = use_readers(monkeypatch, BLOCKED, page_with(POSTING))
    url = job_url()
    assert (await visitor.post(PREVIEWS, json={"url": url})).status_code == 200

    await client.put("/api/v1/profile/me", json=PROFILE)
    checked = await client.post("/api/v1/matches", json={"url": url})
    assert checked.is_success and checked.json()["company"] == "Megaminds IT Services"
    assert (readers.direct_calls, readers.rendered_calls) == (1, 1)


async def test_a_link_is_required(visitor: AsyncClient) -> None:
    assert (await visitor.post(PREVIEWS, json={"url": "  "})).status_code == 422
