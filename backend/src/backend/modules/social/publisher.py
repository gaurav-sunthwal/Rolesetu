"""Sends approved posts when their time comes, and reads back their numbers.

It runs on a timer inside the API (every hour while the API is awake),
and when the outside scheduler wakes the API (`tick`, see router.py). Render's
free plan sleeps the API when idle, so the outside scheduler is what makes a
post go out on time. The timer is slow on purpose: every check wakes the
database, and Neon's free plan counts the time it is awake.

Each account a post goes to is handled on its own: a post can be up on
LinkedIn and fail on Instagram, and the admin panel shows both. A platform that
is briefly down is tried again a few times. A request cut off mid-way is never
retried by itself, since the post may already be up and must not appear twice.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from backend.core.encryption import decrypt_text
from backend.db.session import get_sessionmaker
from backend.modules.social import repository, videos
from backend.modules.social.models import SocialAccount, SocialPost, SocialPostTarget
from backend.modules.social.platforms import linkedin, meta, youtube
from backend.modules.social.platforms.base import (
    PlatformBusyError,
    PostRejectedError,
    Published,
    Stats,
    TokenRejectedError,
)

logger = logging.getLogger(__name__)

# Hourly: each check wakes the database, and Neon's free plan bills the time it is awake.
CHECK_EVERY = timedelta(hours=1)
MAX_POSTS_PER_ROUND = 10
MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=5)
# Longer than a publish can take; a post still "publishing" after this was cut off.
STUCK_AFTER = timedelta(minutes=15)
CUT_OFF = (
    "Publishing was interrupted. Check the account before retrying: the post may already be up."
)
# Numbers are read for a post's first 30 days, at most every 6 hours.
MEASURE_FOR = timedelta(days=30)
MEASURE_EVERY = timedelta(hours=6)
MAX_MEASURED_PER_ROUND = 40


async def send_to_platform(account: SocialAccount, post: SocialPost) -> Published:
    token = decrypt_text(account.access_token)
    text, image_url, video_key = post.text, post.image_url, post.video_key
    if account.platform == "linkedin":
        if video_key:
            raise PostRejectedError("Posting videos to LinkedIn is not supported yet.")
        return await linkedin.publish(
            access_token=token, member_id=account.external_id, text=text, image_url=image_url
        )
    if account.platform == "youtube":
        if not video_key:
            raise PostRejectedError("YouTube needs a video.")
        return await youtube.publish(
            refresh_token=token,
            title=post.youtube_title or text.splitlines()[0][: youtube.MAX_TITLE],
            description=post.youtube_description or text,
            video=await videos.read(video_key),
        )
    video_url = await videos.link(video_key, videos.PLATFORM_SECONDS) if video_key else None
    if account.platform == "facebook":
        if video_url:
            return await meta.publish_facebook_video(
                access_token=token, page_id=account.external_id, text=text, video_url=video_url
            )
        return await meta.publish_facebook(
            access_token=token, page_id=account.external_id, text=text, image_url=image_url
        )
    if account.platform == "instagram":
        if video_url:
            return await meta.publish_instagram_reel(
                access_token=token, account_id=account.external_id, text=text, video_url=video_url
            )
        return await meta.publish_instagram(
            access_token=token, account_id=account.external_id, text=text, image_url=image_url
        )
    raise PostRejectedError(f"Posting to {account.platform} is not supported.")


def outcome(statuses: list[str]) -> str:
    """A post's overall status from where each of its accounts stands."""
    if any(status in ("pending", "publishing") for status in statuses):
        return "scheduled"
    posted = sum(status == "posted" for status in statuses)
    if posted and posted == len(statuses):
        return "posted"
    return "partly_posted" if posted else "failed"


async def _publish_target(
    post: SocialPost, target: SocialPostTarget, account: SocialAccount
) -> None:
    """Sends the post to one account and records what happened on `target`."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        target.status, target.attempts = "publishing", target.attempts + 1
        await db.merge(target)
        await db.commit()

    expired = False
    try:
        published = await send_to_platform(account, post)
        target.status, target.external_url, target.error = "posted", published.url, None
        target.external_id = published.external_id
        target.posted_at = datetime.now(UTC)
    except PlatformBusyError as exc:
        if target.attempts < MAX_ATTEMPTS:
            target.status, target.error = "pending", str(exc)
        else:
            target.status, target.error = "failed", f"{exc} Gave up after {MAX_ATTEMPTS} tries."
    except TokenRejectedError as exc:
        target.status, target.error, expired = "failed", f"{exc} Reconnect the account.", True
    except PostRejectedError as exc:
        target.status, target.error = "failed", str(exc)
    except Exception:
        logger.exception("social post=%s to %s failed", post.id, account.platform)
        target.status, target.error = "failed", "Something went wrong on our side. Try again."

    async with sessionmaker() as db:
        await db.merge(target)
        if expired:
            await repository.mark_account_expired(db, account.id)
        await db.commit()


async def publish_post(post_id: uuid.UUID, now: datetime) -> str:
    """Sends a claimed post to each account still waiting for it. Returns its new status."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        post = await repository.get_post(db, post_id)
        if post is None:
            return "deleted"
        targets = (await repository.targets_of(db, [post_id])).get(post_id, [])

    for target, account in targets:
        if target.status == "pending":
            await _publish_target(post, target, account)

    status = outcome([target.status for target, _ in targets]) if targets else "failed"
    async with sessionmaker() as db:
        stored = await repository.get_post(db, post_id)
        if stored is None:
            return "deleted"
        stored.status = status
        if status == "scheduled":
            # Some account was busy: come back to it in a few minutes.
            stored.scheduled_at = now + RETRY_AFTER
        await db.commit()
    return status


async def _recover_stuck(now: datetime, only: list[uuid.UUID] | None) -> None:
    async with get_sessionmaker()() as db:
        stuck = await repository.stuck_publishing(db, now - STUCK_AFTER, only)
        if not stuck:
            return
        rows = await repository.targets_of(db, stuck)
        for post_id in stuck:
            targets = rows.get(post_id, [])
            for target, _ in targets:
                if target.status == "publishing":
                    target.status, target.error = "failed", CUT_OFF
            post = await repository.get_post(db, post_id)
            if post is not None:
                post.status = (
                    outcome([target.status for target, _ in targets]) if targets else "failed"
                )
        await db.commit()
        logger.warning("social posts recovered after an interrupted publish: %d", len(stuck))


async def publish_due(now: datetime | None = None, only: list[uuid.UUID] | None = None) -> int:
    """Publishes every post whose time has come (or only those in `only`).
    Returns how many were handled.
    """
    now = now or datetime.now(UTC)
    await _recover_stuck(now, only)
    async with get_sessionmaker()() as db:
        claimed = await repository.claim_due(db, now, MAX_POSTS_PER_ROUND, only)
        await db.commit()
    for post_id in claimed:
        try:
            status = await publish_post(post_id, now)
            logger.info("social post=%s -> %s", post_id, status)
        except Exception:
            logger.exception("social post=%s could not be published", post_id)
    return len(claimed)


async def _read_numbers(account: SocialAccount, target: SocialPostTarget) -> Stats | None:
    token = decrypt_text(account.access_token)
    assert target.external_id
    if account.platform == "instagram":
        return await meta.instagram_stats(access_token=token, media_id=target.external_id)
    if account.platform == "youtube":
        return await youtube.stats(refresh_token=token, video_id=target.external_id)
    return None


async def _read_followers(account: SocialAccount) -> int | None:
    token = decrypt_text(account.access_token)
    if account.platform == "instagram":
        return await meta.instagram_followers(access_token=token, account_id=account.external_id)
    if account.platform == "youtube":
        return await youtube.subscribers(refresh_token=token, channel_id=account.external_id)
    return None


async def refresh_numbers(now: datetime | None = None, *, force: bool = False) -> int:
    """Reads the numbers of recent posts whose numbers are older than six hours
    (or all of them, with `force`), and each measured account's followers.
    Returns how many posts were updated."""
    now = now or datetime.now(UTC)
    stale_before = now if force else now - MEASURE_EVERY
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        rows = await repository.targets_needing_numbers(
            db,
            posted_since=now - MEASURE_FOR,
            stale_before=stale_before,
            limit=MAX_MEASURED_PER_ROUND,
        )
    if not rows:
        return 0
    updated = 0
    expired: set[uuid.UUID] = set()
    accounts: dict[uuid.UUID, SocialAccount] = {}
    for target, account in rows:
        accounts[account.id] = account
        if account.id in expired:
            continue
        try:
            found = await _read_numbers(account, target)
        except TokenRejectedError:
            expired.add(account.id)
            continue
        except (PostRejectedError, PlatformBusyError) as exc:
            logger.info("No numbers for target=%s yet: %s", target.id, exc)
            continue
        if found is None:
            continue
        async with sessionmaker() as db:
            await repository.save_numbers(db, target.id, found, now)
            await db.commit()
        updated += 1
    for account in accounts.values():
        if account.id in expired:
            continue
        try:
            followers = await _read_followers(account)
        except (PostRejectedError, PlatformBusyError):
            continue
        async with sessionmaker() as db:
            await repository.set_followers(db, account.id, followers)
            await db.commit()
    if expired:
        async with sessionmaker() as db:
            for account_id in expired:
                await repository.mark_account_expired(db, account_id)
            await db.commit()
    logger.info("social numbers refreshed for %d posts", updated)
    return updated


async def tick(now: datetime | None = None) -> None:
    """Everything that is due: posts first, then numbers. One failure does not stop the other."""
    try:
        await publish_due(now)
    except Exception:
        logger.exception("social publishing round failed")
    try:
        await refresh_numbers(now)
    except Exception:
        logger.exception("social numbers round failed")


async def run_forever() -> None:
    """Checks for due posts and stale numbers every hour while the server runs."""
    while True:
        await tick()
        await asyncio.sleep(CHECK_EVERY.total_seconds())
