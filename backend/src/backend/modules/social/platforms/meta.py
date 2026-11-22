"""Posts to Facebook Pages and Instagram business accounts through Meta's Graph API.

One Meta login connects every Page the admin manages, plus the Instagram
business account linked to each Page. For accounts the app's own admins
manage, this works without Meta's app review. Page tokens made from a
long-lived login do not expire, so these rarely need reconnecting.

Instagram only accepts posts with an image or a video (a reel), which it
downloads itself from a public link: images from this API (see PUBLIC_API_URL),
reels from a short-lived signed R2 link.
"""

import asyncio
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.core.config import get_settings
from backend.modules.social.platforms.base import (
    ConnectedAccount,
    PlatformNotConfiguredError,
    PostRejectedError,
    Published,
    Stats,
    TokenRejectedError,
    make_client,
    send,
)

PLATFORM = "Meta"
SCOPES = ",".join(
    [
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
        "business_management",
        "instagram_basic",
        "instagram_content_publish",
        # Reel numbers: views, reach, watch time. Accounts connected before this
        # was added must reconnect to get them; likes and comments work without it.
        "instagram_manage_insights",
    ]
)
MAX_INSTAGRAM_TEXT = 2200
MAX_FACEBOOK_TEXT = 60000
# Instagram prepares an image before it can be published; usually in seconds.
_READY_CHECKS = 10
_READY_WAIT_SECONDS = 3.0
# A reel takes longer: usually under a minute, sometimes a few.
_REEL_READY_CHECKS = 40
_REEL_READY_WAIT_SECONDS = 5.0
_IMAGE_REFUSED = (
    "Instagram could not use the image. It must be a JPEG, under 8 MB, "
    "between 4:5 and 1.91:1 in shape, and reachable from the internet."
)
_VIDEO_REFUSED = (
    "Instagram could not use the video. It must be an MP4 (H.264 video, AAC sound), "
    "3 to 90 seconds long, ideally 9:16, and under 300 MB."
)
# Reel insights; likes and comments come from the media itself.
_INSIGHTS = "views,reach,saved,shares,ig_reels_avg_watch_time"


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.meta_app_id and settings.meta_app_secret)


def _credentials() -> tuple[str, str]:
    settings = get_settings()
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise PlatformNotConfiguredError("Facebook and Instagram")
    return settings.meta_app_id, settings.meta_app_secret


def _graph() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_version}"


def consent_url(state: str) -> str:
    app_id, _ = _credentials()
    version = get_settings().meta_graph_version
    return f"https://www.facebook.com/{version}/dialog/oauth?" + urlencode(
        {
            "client_id": app_id,
            "redirect_uri": get_settings().meta_redirect_uri,
            "state": state,
            "scope": SCOPES,
            "response_type": "code",
        }
    )


async def exchange_code(code: str) -> list[ConnectedAccount]:
    """Trades the code for a long-lived login, then lists the Pages (and
    their Instagram accounts) it can post to.
    """
    app_id, app_secret = _credentials()
    async with make_client() as client:
        short = await send(
            client,
            PLATFORM,
            "POST",
            f"{_graph()}/oauth/access_token",
            data={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": get_settings().meta_redirect_uri,
                "code": code,
            },
        )
        long = await send(
            client,
            PLATFORM,
            "POST",
            f"{_graph()}/oauth/access_token",
            data={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": str(short.json()["access_token"]),
            },
        )
        user_token = str(long.json()["access_token"])
        pages = await send(
            client,
            PLATFORM,
            "GET",
            f"{_graph()}/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username}",
                "limit": "100",
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )

    accounts: list[ConnectedAccount] = []
    for page in pages.json().get("data", []):
        page_token = str(page["access_token"])
        accounts.append(
            ConnectedAccount(
                platform="facebook",
                external_id=str(page["id"]),
                name=str(page.get("name") or "Facebook Page"),
                access_token=page_token,
                expires_at=None,
            )
        )
        instagram = page.get("instagram_business_account")
        if isinstance(instagram, dict) and instagram.get("id"):
            accounts.append(
                ConnectedAccount(
                    platform="instagram",
                    external_id=str(instagram["id"]),
                    name=f"@{instagram.get('username') or instagram['id']}",
                    # Instagram posts are made with the token of the Page it is linked to.
                    access_token=page_token,
                    expires_at=None,
                )
            )
    return accounts


async def publish_facebook(
    *, access_token: str, page_id: str, text: str, image_url: str | None
) -> Published:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with make_client() as client:
        if image_url:
            created = await send(
                client,
                PLATFORM,
                "POST",
                f"{_graph()}/{page_id}/photos",
                publishes=True,
                headers=headers,
                data={"url": image_url, "caption": text},
            )
        else:
            created = await send(
                client,
                PLATFORM,
                "POST",
                f"{_graph()}/{page_id}/feed",
                publishes=True,
                headers=headers,
                data={"message": text},
            )
    body = created.json()
    post_id = body.get("post_id") or body.get("id")
    return Published(url=f"https://www.facebook.com/{post_id}" if post_id else None)


async def _wait_until_ready(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    container_id: str,
    *,
    checks: int,
    wait_seconds: float,
    refused: str,
) -> None:
    for _ in range(checks):
        state = await send(
            client,
            PLATFORM,
            "GET",
            f"{_graph()}/{container_id}",
            headers=headers,
            params={"fields": "status_code"},
        )
        status = state.json().get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise PostRejectedError(refused)
        await asyncio.sleep(wait_seconds)
    raise PostRejectedError("Instagram took too long to prepare the post. Try again.")


async def _publish_container(
    client: httpx.AsyncClient, headers: dict[str, str], account_id: str, container_id: str
) -> Published:
    published = await send(
        client,
        PLATFORM,
        "POST",
        f"{_graph()}/{account_id}/media_publish",
        publishes=True,
        headers=headers,
        data={"creation_id": container_id},
    )
    media_id = str(published.json()["id"])
    try:
        link = await send(
            client,
            PLATFORM,
            "GET",
            f"{_graph()}/{media_id}",
            headers=headers,
            params={"fields": "permalink"},
        )
        permalink = link.json().get("permalink")
    except Exception:
        # The post is up; only its link could not be read.
        permalink = None
    return Published(url=str(permalink) if permalink else None, external_id=media_id)


async def publish_instagram(
    *, access_token: str, account_id: str, text: str, image_url: str | None
) -> Published:
    if not image_url:
        raise PostRejectedError("Instagram needs an image on every post.")
    headers = {"Authorization": f"Bearer {access_token}"}
    async with make_client() as client:
        container = await send(
            client,
            PLATFORM,
            "POST",
            f"{_graph()}/{account_id}/media",
            headers=headers,
            data={"image_url": image_url, "caption": text},
        )
        container_id = str(container.json()["id"])
        await _wait_until_ready(
            client,
            headers,
            container_id,
            checks=_READY_CHECKS,
            wait_seconds=_READY_WAIT_SECONDS,
            refused=_IMAGE_REFUSED,
        )
        return await _publish_container(client, headers, account_id, container_id)


async def publish_instagram_reel(
    *, access_token: str, account_id: str, text: str, video_url: str
) -> Published:
    """Posts a reel. Instagram downloads the video from `video_url` itself."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with make_client() as client:
        container = await send(
            client,
            PLATFORM,
            "POST",
            f"{_graph()}/{account_id}/media",
            headers=headers,
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": text,
                "share_to_feed": "true",
            },
        )
        container_id = str(container.json()["id"])
        await _wait_until_ready(
            client,
            headers,
            container_id,
            checks=_REEL_READY_CHECKS,
            wait_seconds=_REEL_READY_WAIT_SECONDS,
            refused=_VIDEO_REFUSED,
        )
        return await _publish_container(client, headers, account_id, container_id)


async def publish_facebook_video(
    *, access_token: str, page_id: str, text: str, video_url: str
) -> Published:
    """Posts a video to a Page. Facebook downloads it from `video_url` itself."""
    async with make_client() as client:
        created = await send(
            client,
            PLATFORM,
            "POST",
            f"{_graph()}/{page_id}/videos",
            publishes=True,
            headers={"Authorization": f"Bearer {access_token}"},
            data={"file_url": video_url, "description": text},
        )
    video_id = str(created.json()["id"])
    return Published(
        url=f"https://www.facebook.com/{page_id}/videos/{video_id}", external_id=video_id
    )


def _insight_value(metric: dict[str, Any]) -> int | None:
    values = metric.get("values") or [{}]
    value = values[0].get("value", (metric.get("total_value") or {}).get("value"))
    return int(value) if isinstance(value, int | float) else None


async def instagram_stats(*, access_token: str, media_id: str) -> Stats:
    """A post's numbers. Views, reach and watch time need instagram_manage_insights;
    without it, likes and comments still come back."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with make_client() as client:
        basics = await send(
            client,
            PLATFORM,
            "GET",
            f"{_graph()}/{media_id}",
            headers=headers,
            params={"fields": "like_count,comments_count"},
        )
        found: dict[str, int | None] = {}
        try:
            insights = await send(
                client,
                PLATFORM,
                "GET",
                f"{_graph()}/{media_id}/insights",
                headers=headers,
                params={"metric": _INSIGHTS},
            )
            for metric in insights.json().get("data", []):
                found[str(metric.get("name"))] = _insight_value(metric)
        except TokenRejectedError:
            raise
        except PostRejectedError:
            pass
    body = basics.json()
    return Stats(
        views=found.get("views"),
        reach=found.get("reach"),
        likes=body.get("like_count"),
        comments=body.get("comments_count"),
        shares=found.get("shares"),
        saves=found.get("saved"),
        avg_watch_ms=found.get("ig_reels_avg_watch_time"),
    )


async def instagram_followers(*, access_token: str, account_id: str) -> int | None:
    async with make_client() as client:
        response = await send(
            client,
            PLATFORM,
            "GET",
            f"{_graph()}/{account_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "followers_count"},
        )
    count = response.json().get("followers_count")
    return int(count) if isinstance(count, int) else None
