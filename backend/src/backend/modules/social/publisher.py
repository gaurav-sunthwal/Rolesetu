"""Sends approved posts when their time comes. Runs on a timer inside the API.

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
from backend.modules.social import repository
from backend.modules.social.models import SocialAccount, SocialPost, SocialPostTarget
from backend.modules.social.platforms import linkedin, meta
from backend.modules.social.platforms.base import (
    PlatformBusyError,
    PostRejectedError,
    Published,
    TokenRejectedError,
)

logger = logging.getLogger(__name__)

CHECK_EVERY = timedelta(seconds=60)
MAX_POSTS_PER_ROUND = 10
MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=5)
# Longer than a publish can take; a post still "publishing" after this was cut off.
STUCK_AFTER = timedelta(minutes=15)
CUT_OFF = (
    "Publishing was interrupted. Check the account before retrying: the post may already be up."
)


async def send_to_platform(account: SocialAccount, text: str, image_url: str | None) -> Published:
    token = decrypt_text(account.access_token)
    if account.platform == "linkedin":
        return await linkedin.publish(
            access_token=token, member_id=account.external_id, text=text, image_url=image_url
        )
    if account.platform == "facebook":
        return await meta.publish_facebook(
            access_token=token, page_id=account.external_id, text=text, image_url=image_url
        )
    if account.platform == "instagram":
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
        published = await send_to_platform(account, post.text, post.image_url)
        target.status, target.external_url, target.error = "posted", published.url, None
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


async def run_forever() -> None:
    """Checks for due posts every minute, for as long as the server runs."""
    while True:
        try:
            await publish_due()
        except Exception:
            logger.exception("social publishing round failed")
        await asyncio.sleep(CHECK_EVERY.total_seconds())
