"""Posts to Facebook Pages and Instagram business accounts through Meta's Graph API.

One Meta login connects every Page the admin manages, plus the Instagram
business account linked to each Page. For accounts the app's own admins
manage, this works without Meta's app review. Page tokens made from a
long-lived login do not expire, so these rarely need reconnecting.

Instagram only accepts posts with an image, which it downloads itself from a
public link (see PUBLIC_API_URL).
"""

import asyncio
from urllib.parse import urlencode

from backend.core.config import get_settings
from backend.modules.social.platforms.base import (
    ConnectedAccount,
    PlatformNotConfiguredError,
    PostRejectedError,
    Published,
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
    ]
)
MAX_INSTAGRAM_TEXT = 2200
MAX_FACEBOOK_TEXT = 60000
# Instagram prepares an image before it can be published; usually in seconds.
_READY_CHECKS = 10
_READY_WAIT_SECONDS = 3.0


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
        for _ in range(_READY_CHECKS):
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
                break
            if status in ("ERROR", "EXPIRED"):
                raise PostRejectedError(
                    "Instagram could not use the image. It must be a JPEG, under 8 MB, "
                    "between 4:5 and 1.91:1 in shape, and reachable from the internet."
                )
            await asyncio.sleep(_READY_WAIT_SECONDS)
        else:
            raise PostRejectedError("Instagram took too long to prepare the image. Try again.")

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
    return Published(url=str(permalink) if permalink else None)
