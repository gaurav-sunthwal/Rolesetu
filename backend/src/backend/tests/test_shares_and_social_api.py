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
    assert refused.status_code == 422  # Instagram needs an image or a video

    draft = (
        await admin.post(
            f"{API}/admin/social/posts",
            json={"text": "Know your fit #jobs", "account_ids": [str(linkedin_id)]},
        )
    ).json()
    assert draft["status"] == "draft"

    sent: list[str] = []

    async def fake_send(account: SocialAccount, post: SocialPost) -> Published:
        sent.append(post.text)
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

    async def refuse(account: SocialAccount, post: SocialPost) -> Published:
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


# --- reels, the queue and the numbers ---------------------------------------------

REEL = "social/videos/" + "b" * 32 + ".mp4"


@pytest.fixture
def no_storage(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Keeps reel files away from the real bucket; records what was stored or removed."""
    from backend.core import storage

    touched: list[str] = []

    async def put_stream(key: str, stream: object, *, content_type: str) -> None:
        touched.append(f"put {key}")

    async def signed_url(key: str, *, content_type: str, expires_in: int) -> str:
        return f"https://r2.example.com/{key}?sig=1"

    async def delete_file(key: str) -> None:
        touched.append(f"delete {key}")

    async def signed_upload_url(key: str, *, content_type: str, expires_in: int) -> str:
        return f"https://r2.example.com/{key}?upload=1"

    async def file_size(key: str) -> int | None:
        return None if key.endswith("0" * 32 + ".mp4") else 2048

    async def read_start(key: str, length: int) -> bytes:
        # A key with "c" in it stands for a file that is not an MP4.
        return b"\x89PNG\r\n\x1a\n...." if "c" * 32 in key else b"\x00\x00\x00\x20ftypisom"

    monkeypatch.setattr(storage, "put_stream", put_stream)
    monkeypatch.setattr(storage, "signed_url", signed_url)
    monkeypatch.setattr(storage, "delete_file", delete_file)
    monkeypatch.setattr(storage, "signed_upload_url", signed_upload_url)
    monkeypatch.setattr(storage, "file_size", file_size)
    monkeypatch.setattr(storage, "read_start", read_start)
    return touched


async def test_new_social_routes_are_admin_only(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/admin/social/dashboard")).status_code == 403
    assert (await client.get(f"{API}/admin/social/reels")).status_code == 403
    assert (await client.post(f"{API}/admin/social/check-now")).status_code == 403
    assert (await client.get(f"{API}/admin/social/stats")).status_code == 403
    assert (await client.post(f"{API}/admin/social/stats/refresh")).status_code == 403
    files = {"file": ("r.mp4", b"\x00\x00\x00\x20ftypisom", "video/mp4")}
    assert (await client.post(f"{API}/admin/social/videos", files=files)).status_code == 403
    upload_url = f"{API}/admin/social/videos/upload-url"
    assert (await client.post(upload_url, json={"size_bytes": 10})).status_code == 403


async def test_a_reel_upload_must_be_an_mp4(admin: AsyncClient, no_storage: list[str]) -> None:
    png = {"file": ("r.mp4", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "video/mp4")}
    assert (await admin.post(f"{API}/admin/social/videos", files=png)).status_code == 422

    mp4 = {"file": ("r.mp4", b"\x00\x00\x00\x20ftypisom" + b"0" * 100, "video/mp4")}
    stored = (await admin.post(f"{API}/admin/social/videos", files=mp4)).json()
    assert stored["key"].startswith("social/videos/")
    assert stored["url"].startswith("https://r2.example.com/")
    assert no_storage == [f"put {stored['key']}"]


async def test_a_reel_can_be_uploaded_straight_to_storage(
    admin: AsyncClient, no_storage: list[str]
) -> None:
    too_big = await admin.post(f"{API}/admin/social/videos/upload-url", json={"size_bytes": 10**12})
    assert too_big.status_code == 422

    started = (
        await admin.post(f"{API}/admin/social/videos/upload-url", json={"size_bytes": 2048})
    ).json()
    assert started["key"].startswith("social/videos/")
    assert started["upload_url"].startswith("https://r2.example.com/")

    confirmed = await admin.post(f"{API}/admin/social/videos/confirm", json={"key": started["key"]})
    assert confirmed.json()["size_bytes"] == 2048

    missing = "social/videos/" + "0" * 32 + ".mp4"
    assert (
        await admin.post(f"{API}/admin/social/videos/confirm", json={"key": missing})
    ).status_code == 422

    not_mp4 = "social/videos/" + "c" * 32 + ".mp4"
    refused = await admin.post(f"{API}/admin/social/videos/confirm", json={"key": not_mp4})
    assert refused.status_code == 422
    assert f"delete {not_mp4}" in no_storage

    forged = await admin.post(f"{API}/admin/social/videos/confirm", json={"key": "../secrets"})
    assert forged.status_code == 422


async def test_a_reel_goes_to_instagram_and_youtube_and_is_measured(
    admin: AsyncClient, no_storage: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.modules.social.platforms.base import Stats

    instagram_id = await add_account(admin, "instagram")
    youtube_id = await add_account(admin, "youtube")
    accounts = [str(instagram_id), str(youtube_id)]

    untitled = await admin.post(
        f"{API}/admin/social/posts",
        json={"text": "POV", "video_key": REEL, "account_ids": accounts},
    )
    assert untitled.status_code == 422  # YouTube needs a title

    draft = (
        await admin.post(
            f"{API}/admin/social/posts",
            json={
                "text": "POV: subah ka pehla email",
                "video_key": REEL,
                "youtube_title": "POV #shorts",
                "account_ids": accounts,
            },
        )
    ).json()
    assert draft["video_url"].startswith("https://r2.example.com/")

    # Scheduled, then moved to a new time without going back to a draft.
    now = datetime.now(UTC)
    ours = [uuid.UUID(draft["id"])]
    first = (now + timedelta(hours=5)).isoformat()
    await admin.post(f"{API}/admin/social/posts/{draft['id']}/schedule", json={"at": first})
    moved = (now + timedelta(hours=1)).isoformat()
    rescheduled = await admin.post(
        f"{API}/admin/social/posts/{draft['id']}/schedule", json={"at": moved}
    )
    assert rescheduled.json()["status"] == "scheduled"
    assert rescheduled.json()["scheduled_at"].startswith(moved[:16])

    queue = (await admin.get(f"{API}/admin/social/posts?view=queue")).json()
    assert draft["id"] in [item["id"] for item in queue["items"]]

    sent: list[tuple[str, str | None]] = []

    async def fake_send(account: SocialAccount, post: SocialPost) -> Published:
        sent.append((account.platform, post.video_key))
        return Published(url=f"https://{account.platform}.example.com/1", external_id="ext1")

    monkeypatch.setattr(publisher, "send_to_platform", fake_send)
    await publisher.publish_due(now + timedelta(hours=2), only=ours)
    assert sorted(sent) == [("instagram", REEL), ("youtube", REEL)]

    posted = (await admin.get(f"{API}/admin/social/posts?view=posted")).json()
    assert draft["id"] in [item["id"] for item in posted["items"]]
    queue = (await admin.get(f"{API}/admin/social/posts?view=queue")).json()
    assert draft["id"] not in [item["id"] for item in queue["items"]]

    async def numbers(account: SocialAccount, target: object) -> Stats:
        if account.platform == "instagram":
            return Stats(views=100, reach=90, likes=3, shares=1, saves=2, avg_watch_ms=3000)
        return Stats(views=50, likes=1, comments=0)

    async def followers(account: SocialAccount) -> int:
        return 4

    monkeypatch.setattr(publisher, "_read_numbers", numbers)
    monkeypatch.setattr(publisher, "_read_followers", followers)
    assert await publisher.refresh_numbers(now + timedelta(hours=3)) >= 2

    post = next(
        item
        for item in (await admin.get(f"{API}/admin/social/posts?view=posted")).json()["items"]
        if item["id"] == draft["id"]
    )
    by_platform = {target["platform"]: target for target in post["targets"]}
    assert by_platform["instagram"]["avg_watch_ms"] == 3000
    assert by_platform["youtube"]["views"] == 50

    stats = (await admin.get(f"{API}/admin/social/stats?days=7")).json()
    totals = {row["platform"]: row for row in stats["platforms"]}
    assert totals["instagram"]["views"] >= 100
    assert totals["instagram"]["avg_watch_seconds"] is not None
    assert stats["refreshed_at"] is not None
    assert 4 in [account["followers"] for account in stats["accounts"]]

    # Numbers are not read again within six hours.
    assert await publisher.refresh_numbers(now + timedelta(hours=4)) == 0

    # A later reading: the table shows what changed since the previous one.
    async def more(account: SocialAccount, target: object) -> Stats:
        return Stats(views=160 if account.platform == "instagram" else 70, likes=4)

    monkeypatch.setattr(publisher, "_read_numbers", more)
    await publisher.refresh_numbers(now + timedelta(hours=10))
    reels = (await admin.get(f"{API}/admin/social/reels")).json()
    reel = next(item for item in reels if item["id"] == draft["id"])
    assert reel["views"] == 230
    assert reel["views_by_platform"] == {"instagram": 160, "youtube": 70}
    assert reel["views_since_refresh"] == 80
    assert reel["title"] == "POV #shorts"

    board = (await admin.get(f"{API}/admin/social/dashboard")).json()
    assert board["total_views"] >= 230
    assert board["posted_total"] >= 1


async def test_post_now_publishes_straight_away(
    admin: AsyncClient, no_storage: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    instagram_id = await add_account(admin, "instagram")
    draft = (
        await admin.post(
            f"{API}/admin/social/posts",
            json={"text": "Now", "video_key": REEL, "account_ids": [str(instagram_id)]},
        )
    ).json()
    sent: list[str] = []

    async def fake_send(account: SocialAccount, post: SocialPost) -> Published:
        sent.append(post.text)
        return Published(url="https://instagram.example.com/2", external_id="m2")

    monkeypatch.setattr(publisher, "send_to_platform", fake_send)
    await admin.post(f"{API}/admin/social/posts/{draft['id']}/schedule", json={})
    assert sent == ["Now"]


async def test_deleting_a_reel_post_removes_its_video(
    admin: AsyncClient, no_storage: list[str]
) -> None:
    instagram_id = await add_account(admin, "instagram")
    draft = (
        await admin.post(
            f"{API}/admin/social/posts",
            json={"text": "x", "video_key": REEL, "account_ids": [str(instagram_id)]},
        )
    ).json()
    assert (await admin.delete(f"{API}/admin/social/posts/{draft['id']}")).status_code == 204
    assert f"delete {REEL}" in no_storage


async def test_the_wake_up_route_needs_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks: list[bool] = []

    async def fake_tick() -> None:
        ticks.append(True)

    monkeypatch.setattr(publisher, "tick", fake_tick)
    url = f"{API}/internal/social/tick"
    async with anonymous() as visitor:
        monkeypatch.setattr(get_settings(), "cron_secret", None)
        assert (await visitor.post(url, headers={"x-cron-secret": "x"})).status_code == 404
        monkeypatch.setattr(get_settings(), "cron_secret", "s3cret")
        assert (await visitor.post(url)).status_code == 404
        assert (await visitor.post(url, headers={"x-cron-secret": "wrong"})).status_code == 404
        assert (await visitor.post(url, headers={"x-cron-secret": "s3cret"})).status_code == 202
    assert ticks == [True]
