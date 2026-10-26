"""Shared score cards and the admin Social section, through the API and database.

Skipped until migration c3e8a1f4d2b9 has been applied to the database the
tests use.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.main import app
from backend.modules.admin.models import AdminAction
from backend.modules.matches.models import Job, Match
from backend.modules.social import publisher
from backend.modules.social.models import SocialAccount, SocialPost
from backend.modules.social.platforms.base import PostRejectedError, Published
from backend.tests.conftest import ClientFactory

API = "/api/v1"


@pytest.fixture(autouse=True)
async def _needs_tables() -> None:
    async with get_sessionmaker()() as db:
        found = await db.execute(text("select to_regclass('public.social_posts')"))
        if found.scalar_one() is None:
            pytest.skip("Apply migration c3e8a1f4d2b9 to run these tests.")


async def user_id_of(client: AsyncClient) -> uuid.UUID:
    response = await client.get(f"{API}/users/me")
    return uuid.UUID(response.json()["id"])


async def add_match(client: AsyncClient, *, status: str = "completed") -> uuid.UUID:
    user_id = await user_id_of(client)
    async with get_sessionmaker()() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_id,
            role="Backend Engineer",
            company="Acme",
            jd_text="x" * 300,
            content_hash=uuid.uuid4().hex,
        )
        match = Match(
            id=uuid.uuid4(),
            user_id=user_id,
            job_id=job.id,
            profile_version=1,
            status=status,
            score=82 if status == "completed" else None,
            skill_results=[
                {"name": "Go", "required": True, "verdict": "strong"},
                {"name": "Kubernetes", "required": True, "verdict": "missing"},
            ],
            gaps=["Kubernetes"],
        )
        db.add_all([job, match])
        await db.commit()
        return match.id


def anonymous() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_a_shared_score_is_public_and_can_be_taken_back(client: AsyncClient) -> None:
    match_id = await add_match(client)
    first = await client.post(f"{API}/matches/{match_id}/share", json={})
    assert first.status_code == 200
    card = first.json()
    assert card["score"] == 82
    assert card["matched"] == ["Go"]
    assert card["gaps"] == []  # hidden unless asked for

    again = await client.post(f"{API}/matches/{match_id}/share", json={"show_gaps": True})
    assert again.json()["slug"] == card["slug"]
    assert again.json()["gaps"] == ["Kubernetes"]

    async with anonymous() as visitor:
        public = await visitor.get(f"{API}/public/shares/{card['slug']}")
        assert public.status_code == 200
        assert set(public.json()) == {
            "slug",
            "role",
            "company",
            "score",
            "matched",
            "gaps",
            "created_at",
        }

        assert (await client.delete(f"{API}/shares/{card['slug']}")).status_code == 204
        assert (await visitor.get(f"{API}/public/shares/{card['slug']}")).status_code == 404


async def test_only_the_owner_can_share_or_unshare(make_client: ClientFactory) -> None:
    owner, other = make_client(), make_client()
    match_id = await add_match(owner)
    assert (await other.post(f"{API}/matches/{match_id}/share", json={})).status_code == 404
    slug = (await owner.post(f"{API}/matches/{match_id}/share", json={})).json()["slug"]
    assert (await other.delete(f"{API}/shares/{slug}")).status_code == 404


async def test_an_unfinished_check_cannot_be_shared(client: AsyncClient) -> None:
    match_id = await add_match(client, status="pending")
    assert (await client.post(f"{API}/matches/{match_id}/share", json={})).status_code == 409


@pytest.fixture
async def admin(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient]:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    email = f"{client.headers['x-test-uid']}@example.com"
    monkeypatch.setattr(get_settings(), "admin_emails", [email])
    yield client
    async with get_sessionmaker()() as db:
        await db.execute(delete(SocialPost).where(SocialPost.created_by == email))
        await db.execute(delete(SocialAccount).where(SocialAccount.connected_by == email))
        await db.execute(delete(AdminAction).where(AdminAction.admin_email == email))
        await db.commit()


async def add_account(admin: AsyncClient, platform: str) -> uuid.UUID:
    account = SocialAccount(
        id=uuid.uuid4(),
        platform=platform,
        external_id=uuid.uuid4().hex,
        name=f"Test {platform}",
        access_token="not-a-real-token",
        connected_by=f"{admin.headers['x-test-uid']}@example.com",
        status="active",
    )
    async with get_sessionmaker()() as db:
        db.add(account)
        await db.commit()
    return account.id


async def test_social_is_admin_only(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/admin/social")).status_code == 403
    assert (await client.get(f"{API}/admin/social/posts")).status_code == 403


async def test_a_draft_is_only_posted_once_approved(
    admin: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    linkedin_id = await add_account(admin, "linkedin")
    instagram_id = await add_account(admin, "instagram")

    refused = await admin.post(
        f"{API}/admin/social/posts", json={"text": "Hi", "account_ids": [str(instagram_id)]}
    )
    assert refused.status_code == 422  # Instagram needs an image

    draft = (
        await admin.post(
            f"{API}/admin/social/posts",
            json={"text": "Know your fit #jobs", "account_ids": [str(linkedin_id)]},
        )
    ).json()
    assert draft["status"] == "draft"

    sent: list[str] = []

    async def fake_send(account: SocialAccount, text: str, image_url: str | None) -> Published:
        sent.append(text)
        return Published(url="https://www.linkedin.com/feed/update/urn:li:share:1/")

    monkeypatch.setattr(publisher, "send_to_platform", fake_send)
    # Only this test's post: the database may hold real queued posts.
    ours = [uuid.UUID(draft["id"])]
    now = datetime.now(UTC)
    await publisher.publish_due(now + timedelta(minutes=1), only=ours)
    assert sent == []  # a draft is never published

    later = (now + timedelta(hours=1)).isoformat()
    scheduled = await admin.post(
        f"{API}/admin/social/posts/{draft['id']}/schedule", json={"at": later}
    )
    assert scheduled.json()["status"] == "scheduled"
    await publisher.publish_due(now + timedelta(minutes=1), only=ours)
    assert sent == []  # not yet its time

    await publisher.publish_due(now + timedelta(hours=2), only=ours)
    assert sent == ["Know your fit #jobs"]
    page = (await admin.get(f"{API}/admin/social/posts")).json()
    post = next(item for item in page["items"] if item["id"] == draft["id"])
    assert post["status"] == "posted"
    assert post["targets"][0]["external_url"].startswith("https://www.linkedin.com/")


async def test_a_refused_post_is_reported_and_can_be_retried(
    admin: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    account_id = await add_account(admin, "facebook")
    draft = (
        await admin.post(
            f"{API}/admin/social/posts", json={"text": "Hi", "account_ids": [str(account_id)]}
        )
    ).json()

    async def refuse(account: SocialAccount, text: str, image_url: str | None) -> Published:
        raise PostRejectedError("Meta refused the post: duplicate")

    monkeypatch.setattr(publisher, "send_to_platform", refuse)
    await admin.post(f"{API}/admin/social/posts/{draft['id']}/schedule", json={})
    await publisher.publish_due(
        datetime.now(UTC) + timedelta(seconds=5), only=[uuid.UUID(draft["id"])]
    )

    page = (await admin.get(f"{API}/admin/social/posts")).json()
    post = next(item for item in page["items"] if item["id"] == draft["id"])
    assert post["status"] == "failed"
    assert "duplicate" in post["targets"][0]["error"]

    retried = await admin.post(f"{API}/admin/social/posts/{draft['id']}/retry")
    assert retried.json()["status"] == "scheduled"
    assert retried.json()["targets"][0]["status"] == "pending"
