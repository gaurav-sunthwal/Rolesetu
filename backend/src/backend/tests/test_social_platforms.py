"""Social posting without a database: the platform clients against fake
LinkedIn and Meta servers, and the rules that decide what may be posted.
"""

import json
from collections.abc import Callable

import httpx
import pymupdf
import pytest

from backend.core.config import get_settings
from backend.core.exceptions import ValidationFailedError
from backend.modules.shares.service import matched_skills
from backend.modules.social import images, publisher, service, videos
from backend.modules.social.platforms import base, linkedin, meta, youtube
from backend.modules.social.platforms.base import (
    OutcomeUnknownError,
    PlatformBusyError,
    PostRejectedError,
    TokenRejectedError,
)

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def fake_platform(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[httpx.Request]]:
    """Routes every platform request to `handler`, and records the requests."""

    def install(handler: Handler) -> list[httpx.Request]:
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        def client() -> httpx.AsyncClient:
            return httpx.AsyncClient(transport=httpx.MockTransport(recording))

        monkeypatch.setattr(linkedin, "make_client", client)
        monkeypatch.setattr(meta, "make_client", client)
        monkeypatch.setattr(youtube, "make_client", lambda seconds=None: client())
        return seen

    return install


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "linkedin_client_id", "li-id")
    monkeypatch.setattr(settings, "linkedin_client_secret", "li-secret")
    monkeypatch.setattr(settings, "meta_app_id", "meta-id")
    monkeypatch.setattr(settings, "meta_app_secret", "meta-secret")
    monkeypatch.setattr(settings, "youtube_client_id", "yt-id")
    monkeypatch.setattr(settings, "youtube_client_secret", "yt-secret")


def test_linkedin_text_is_literal_except_hashtags() -> None:
    text = "Know your fit (free) - see rolesetu_app @ 100% #JobSearch #AI"
    assert linkedin.to_commentary(text) == (
        r"Know your fit \(free\) - see rolesetu\_app \@ 100% "
        r"{hashtag|\#|JobSearch} {hashtag|\#|AI}"
    )


async def test_linkedin_text_post(fake_platform: Callable[[Handler], list[httpx.Request]]) -> None:
    seen = fake_platform(
        lambda request: httpx.Response(201, headers={"x-restli-id": "urn:li:share:42"})
    )
    published = await linkedin.publish(
        access_token="tok", member_id="abc", text="Hello", image_url=None
    )
    assert published.url == "https://www.linkedin.com/feed/update/urn:li:share:42/"
    body = json.loads(seen[0].content)
    assert body["author"] == "urn:li:person:abc"
    assert body["commentary"] == "Hello"
    assert "content" not in body
    assert seen[0].headers["authorization"] == "Bearer tok"
    assert seen[0].headers["linkedin-version"] == get_settings().linkedin_api_version


async def test_linkedin_image_post_uploads_first(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "img.example.com":
            return httpx.Response(200, content=b"jpeg-bytes")
        if "initializeUpload" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "value": {
                        "uploadUrl": "https://upload.example.com/x",
                        "image": "urn:li:image:9",
                    }
                },
            )
        if request.url.host == "upload.example.com":
            return httpx.Response(201)
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:1"})

    seen = fake_platform(handler)
    await linkedin.publish(
        access_token="tok", member_id="abc", text="Hi", image_url="https://img.example.com/a.jpg"
    )
    assert [request.method for request in seen] == ["GET", "POST", "PUT", "POST"]
    assert seen[2].content == b"jpeg-bytes"
    assert json.loads(seen[3].content)["content"] == {"media": {"id": "urn:li:image:9"}}


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, {"message": "Expired"}, TokenRejectedError),
        (400, {"error": {"message": "Bad token", "code": 190}}, TokenRejectedError),
        (429, {"message": "Slow down"}, PlatformBusyError),
        (503, {}, PlatformBusyError),
        (422, {"message": "Duplicate post"}, PostRejectedError),
    ],
)
async def test_platform_failures_are_sorted(
    fake_platform: Callable[[Handler], list[httpx.Request]],
    status: int,
    body: dict[str, object],
    error: type[Exception],
) -> None:
    fake_platform(lambda request: httpx.Response(status, json=body))
    with pytest.raises(error):
        await linkedin.publish(access_token="tok", member_id="abc", text="Hi", image_url=None)


async def test_a_cut_off_publish_is_never_called_busy(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    fake_platform(handler)
    # Retrying could post twice, so it must not look like a safe-to-retry failure.
    with pytest.raises(OutcomeUnknownError):
        await linkedin.publish(access_token="tok", member_id="abc", text="Hi", image_url=None)


async def test_a_slow_step_before_publishing_is_safe_to_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PlatformBusyError):
            await base.send(client, "Meta", "GET", "https://graph.example.com/x")


async def test_meta_login_finds_pages_and_their_instagram(
    configured: None, fake_platform: Callable[[Handler], list[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/access_token"):
            return httpx.Response(200, json={"access_token": "user-token"})
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "p1",
                        "name": "Rolesetu",
                        "access_token": "page-token",
                        "instagram_business_account": {"id": "ig1", "username": "rolesetu"},
                    },
                    {"id": "p2", "name": "Side page", "access_token": "page-token-2"},
                ]
            },
        )

    seen = fake_platform(handler)
    accounts = await meta.exchange_code("code")
    assert [(a.platform, a.external_id, a.name) for a in accounts] == [
        ("facebook", "p1", "Rolesetu"),
        ("instagram", "ig1", "@rolesetu"),
        ("facebook", "p2", "Side page"),
    ]
    assert accounts[1].access_token == "page-token"
    # No secret or token ever travels in a URL, where logs would keep it.
    assert all("meta-secret" not in str(r.url) and "user-token" not in str(r.url) for r in seen)


async def test_instagram_waits_for_the_image_then_publishes(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/ig1/media"):
            return httpx.Response(200, json={"id": "container"})
        if path.endswith("/container"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "m1"})
        return httpx.Response(200, json={"permalink": "https://www.instagram.com/p/abc/"})

    fake_platform(handler)
    published = await meta.publish_instagram(
        access_token="t", account_id="ig1", text="Hi", image_url="https://x.example.com/a.jpg"
    )
    assert published.url == "https://www.instagram.com/p/abc/"


async def test_instagram_refuses_a_post_without_an_image() -> None:
    with pytest.raises(PostRejectedError):
        await meta.publish_instagram(access_token="t", account_id="ig1", text="Hi", image_url=None)


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["posted", "posted"], "posted"),
        (["posted", "failed"], "partly_posted"),
        (["failed"], "failed"),
        (["posted", "pending"], "scheduled"),
    ],
)
def test_a_posts_status_follows_its_accounts(statuses: list[str], expected: str) -> None:
    assert publisher.outcome(statuses) == expected


def test_posts_that_a_platform_would_refuse_are_stopped_early() -> None:
    service.check_fits("Hi", None, {"linkedin", "facebook"})
    with pytest.raises(ValidationFailedError, match="Instagram needs an image"):
        service.check_fits("Hi", None, {"instagram"})
    with pytest.raises(ValidationFailedError, match="Instagram allows 2200"):
        service.check_fits("x" * 2500, "https://x.example.com/a.jpg", {"instagram"})


def test_connect_state_is_bound_to_provider_and_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from backend.core import encryption
    from backend.modules.admin.dependencies import Admin

    settings = get_settings()
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "admin_emails", ["boss@example.com"])
    monkeypatch.setattr(settings, "linkedin_client_id", "li-id")
    monkeypatch.setattr(settings, "linkedin_client_secret", "li-secret")
    encryption._get_fernet.cache_clear()
    try:
        url = service.connect_url(Admin(email="boss@example.com"), "linkedin")
        state = httpx.URL(url).params["state"]
        assert service._admin_from_state(state, "linkedin") == "boss@example.com"
        with pytest.raises(service.InvalidConnectStateError):
            service._admin_from_state(state, "meta")
        monkeypatch.setattr(settings, "admin_emails", [])
        with pytest.raises(service.InvalidConnectStateError):
            service._admin_from_state(state, "linkedin")
        with pytest.raises(service.InvalidConnectStateError):
            service._admin_from_state("forged", "linkedin")
    finally:
        encryption._get_fernet.cache_clear()


def test_uploaded_images_become_jpeg() -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 30), True)
    pixmap.clear_with(180)
    jpeg = images.to_jpeg(pixmap.tobytes("png"))
    assert jpeg.startswith(b"\xff\xd8\xff")
    with pytest.raises(ValidationFailedError):
        images.to_jpeg(b"not an image")


def test_share_cards_list_required_strong_skills_first() -> None:
    results = [
        {"name": "Docker", "required": False, "verdict": "strong"},
        {"name": "SQL", "required": True, "verdict": "partial"},
        {"name": "Go", "required": True, "verdict": "strong"},
        {"name": "Rust", "required": True, "verdict": "missing"},
    ]
    assert matched_skills(results) == ["Go", "SQL", "Docker"]


# --- reels, YouTube and numbers --------------------------------------------------


async def test_instagram_reel_is_fetched_by_instagram_then_published(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/ig1/media"):
            return httpx.Response(200, json={"id": "container"})
        if path.endswith("/container"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "m9"})
        return httpx.Response(200, json={"permalink": "https://www.instagram.com/reel/abc/"})

    seen = fake_platform(handler)
    published = await meta.publish_instagram_reel(
        access_token="t", account_id="ig1", text="POV", video_url="https://r2.example.com/v.mp4"
    )
    assert published.url == "https://www.instagram.com/reel/abc/"
    assert published.external_id == "m9"
    form = dict(httpx.QueryParams(seen[0].content.decode()))
    assert form["media_type"] == "REELS"
    assert form["video_url"] == "https://r2.example.com/v.mp4"


async def test_a_reel_instagram_cannot_use_is_explained(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "container"})
        return httpx.Response(200, json={"status_code": "ERROR"})

    fake_platform(handler)
    with pytest.raises(PostRejectedError, match="MP4"):
        await meta.publish_instagram_reel(
            access_token="t", account_id="ig1", text="x", video_url="https://r2.example.com/v.mp4"
        )


async def test_instagram_numbers_include_watch_time(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/insights"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"name": "views", "values": [{"value": 133}]},
                        {"name": "reach", "values": [{"value": 93}]},
                        {"name": "shares", "values": [{"value": 1}]},
                        {"name": "saved", "values": [{"value": 2}]},
                        {"name": "ig_reels_avg_watch_time", "values": [{"value": 3085}]},
                    ]
                },
            )
        return httpx.Response(200, json={"like_count": 3, "comments_count": 0})

    fake_platform(handler)
    found = await meta.instagram_stats(access_token="t", media_id="m9")
    assert found == base.Stats(
        views=133, reach=93, likes=3, comments=0, shares=1, saves=2, avg_watch_ms=3085
    )


async def test_instagram_numbers_without_insights_permission_keep_likes(
    fake_platform: Callable[[Handler], list[httpx.Request]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/insights"):
            return httpx.Response(400, json={"error": {"message": "permission", "code": 10}})
        return httpx.Response(200, json={"like_count": 5, "comments_count": 1})

    fake_platform(handler)
    found = await meta.instagram_stats(access_token="t", media_id="m9")
    assert (found.likes, found.comments, found.views) == (5, 1, None)


async def test_youtube_uploads_a_short_without_tokens_in_urls(
    configured: None, fake_platform: Callable[[Handler], list[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access-1"})
        if request.method == "POST":
            return httpx.Response(200, headers={"location": "https://upload.example.com/s1"})
        return httpx.Response(200, json={"id": "vid42"})

    seen = fake_platform(handler)
    published = await youtube.publish(
        refresh_token="refresh-1", title="POV #shorts", description="d", video=b"mp4bytes"
    )
    assert published.url == "https://www.youtube.com/shorts/vid42"
    assert published.external_id == "vid42"
    started = json.loads(seen[1].content)
    assert started["snippet"]["title"] == "POV #shorts"
    assert started["status"]["privacyStatus"] == "public"
    assert seen[2].content == b"mp4bytes"
    assert seen[2].headers["authorization"] == "Bearer access-1"
    assert all("refresh-1" not in str(r.url) and "access-1" not in str(r.url) for r in seen)


async def test_a_revoked_youtube_sign_in_asks_to_reconnect(
    configured: None, fake_platform: Callable[[Handler], list[httpx.Request]]
) -> None:
    fake_platform(lambda request: httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(TokenRejectedError):
        await youtube.stats(refresh_token="old", video_id="vid42")


async def test_youtube_connect_needs_a_lasting_sign_in(
    configured: None, fake_platform: Callable[[Handler], list[httpx.Request]]
) -> None:
    fake_platform(lambda request: httpx.Response(200, json={"access_token": "a"}))
    with pytest.raises(PostRejectedError, match="lasting sign-in"):
        await youtube.exchange_code("code")


async def test_youtube_connect_finds_the_channel(
    configured: None, fake_platform: Callable[[Handler], list[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})
        return httpx.Response(
            200, json={"items": [{"id": "UC1", "snippet": {"title": "Rolesetu"}}]}
        )

    fake_platform(handler)
    [account] = await youtube.exchange_code("code")
    assert (account.platform, account.external_id, account.name) == ("youtube", "UC1", "Rolesetu")
    assert account.access_token == "r"


def test_reel_posts_that_a_platform_would_refuse_are_stopped_early() -> None:
    reel = "social/videos/" + "a" * 32 + ".mp4"
    service.check_fits("Hi", None, {"instagram", "facebook"}, video_key=reel)
    service.check_fits("Hi", None, {"youtube"}, video_key=reel, youtube_title="POV")
    with pytest.raises(ValidationFailedError, match="YouTube needs a video"):
        service.check_fits("Hi", "https://x.example.com/a.jpg", {"youtube"}, youtube_title="t")
    with pytest.raises(ValidationFailedError, match="title"):
        service.check_fits("Hi", None, {"youtube"}, video_key=reel)
    with pytest.raises(ValidationFailedError, match="LinkedIn"):
        service.check_fits("Hi", None, {"linkedin"}, video_key=reel)
    with pytest.raises(ValidationFailedError, match="not both"):
        service.check_fits("Hi", "https://x.example.com/a.jpg", {"facebook"}, video_key=reel)


def test_only_mp4_files_are_taken_as_reels() -> None:
    assert videos.is_mp4(b"\x00\x00\x00\x20ftypisom")
    assert not videos.is_mp4(b"\x89PNG\r\n\x1a\n....")
    assert not videos.is_mp4(b"")
