"""The admin panel's Social section: connecting accounts and managing the queue.

A post is a draft until an admin schedules it. Scheduling is the approval:
nothing reaches a platform without it. The publisher (publisher.py) sends
scheduled posts when their time comes.
"""

import asyncio
import contextlib
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.encryption import decrypt_text, encrypt_text
from backend.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.modules.admin.dependencies import Admin
from backend.modules.social import images, repository, videos
from backend.modules.social.models import SocialAccount, SocialMetricSnapshot, SocialPost
from backend.modules.social.platforms import linkedin, meta, youtube
from backend.modules.social.schemas import (
    NextPost,
    PlatformLink,
    PlatformTotals,
    PlatformViews,
    PostView,
    Provider,
    ProviderStatus,
    ReelStats,
    SocialAccountRead,
    SocialDashboard,
    SocialOverview,
    SocialPostRead,
    SocialPostWrite,
    SocialStats,
    SocialTargetRead,
    VideoUploaded,
    VideoUploadUrl,
)

logger = logging.getLogger(__name__)

STATE_VALID_SECONDS = 600
TEXT_LIMITS: dict[str, int] = {
    "linkedin": linkedin.MAX_TEXT,
    "facebook": meta.MAX_FACEBOOK_TEXT,
    "instagram": meta.MAX_INSTAGRAM_TEXT,
    "youtube": youtube.MAX_DESCRIPTION,
}
PLATFORM_NAMES: dict[str, str] = {
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "youtube": "YouTube",
}
# Posts a draft or scheduled post can still be changed in.
_EDITABLE = ("draft", "scheduled")


class InvalidConnectStateError(Exception):
    """The callback's `state` is missing, forged, too old or for someone no longer an admin."""


def _account_read(account: SocialAccount) -> SocialAccountRead:
    return SocialAccountRead(
        id=account.id,
        platform=account.platform,  # type: ignore[arg-type]
        name=account.name,
        status=account.status,  # type: ignore[arg-type]
        followers=account.followers,
        expires_at=account.expires_at,
        connected_by=account.connected_by,
        created_at=account.created_at,
    )


async def overview(db: AsyncSession) -> SocialOverview:
    return SocialOverview(
        providers=[
            ProviderStatus(provider="linkedin", configured=linkedin.is_configured()),
            ProviderStatus(provider="meta", configured=meta.is_configured()),
            ProviderStatus(provider="youtube", configured=youtube.is_configured()),
        ],
        accounts=[_account_read(account) for account in await repository.list_accounts(db)],
    )


def connect_url(admin: Admin, provider: Provider) -> str:
    """The platform's consent page. `state` carries which admin asked, encrypted,
    because the callback arrives without our login header.
    """
    state = encrypt_text(f"{provider}|{admin.email}|{int(time.time())}")
    if provider == "linkedin":
        return linkedin.consent_url(state)
    if provider == "youtube":
        return youtube.consent_url(state)
    return meta.consent_url(state)


def _admin_from_state(state: str, provider: Provider) -> str:
    try:
        stated_provider, email, issued = decrypt_text(state).split("|", 2)
        fresh = time.time() - int(issued) <= STATE_VALID_SECONDS
    except Exception as exc:
        raise InvalidConnectStateError from exc
    admins = {address.lower() for address in get_settings().admin_emails}
    if stated_provider != provider or not fresh or email.lower() not in admins:
        raise InvalidConnectStateError
    return email


async def finish_connecting(db: AsyncSession, *, provider: Provider, code: str, state: str) -> int:
    """Saves every account the login gave us. Returns how many."""
    email = _admin_from_state(state, provider)
    if provider == "linkedin":
        accounts = await linkedin.exchange_code(code)
    elif provider == "youtube":
        accounts = await youtube.exchange_code(code)
    else:
        accounts = await meta.exchange_code(code)
    for account in accounts:
        await repository.upsert_account(
            db,
            platform=account.platform,
            external_id=account.external_id,
            name=account.name,
            encrypted_token=encrypt_text(account.access_token),
            expires_at=account.expires_at,
            connected_by=email,
        )
    return len(accounts)


async def disconnect(db: AsyncSession, *, admin: Admin, account_id: uuid.UUID) -> None:
    """Forgets the account and its token. Posts already up stay up."""
    if not await repository.delete_account(db, account_id):
        raise NotFoundError("That account is not connected.")


async def upload_image(data: bytes) -> str:
    return await images.save(data)


async def start_video_upload(size_bytes: int) -> VideoUploadUrl:
    key, url = await videos.start_upload(size_bytes)
    return VideoUploadUrl(key=key, upload_url=url)


async def confirm_video(key: str) -> VideoUploaded:
    size = await videos.confirm(key)
    return VideoUploaded(key=key, url=await videos.link(key), size_bytes=size)


async def upload_video(upload: UploadFile) -> VideoUploaded:
    key, size = await videos.save(upload)
    return VideoUploaded(key=key, url=await videos.link(key), size_bytes=size)


def _post_read(
    post: SocialPost, targets: list[repository.TargetRow], video_url: str | None
) -> SocialPostRead:
    return SocialPostRead(
        id=post.id,
        text=post.text,
        image_url=post.image_url,
        video_key=post.video_key,
        video_url=video_url,
        youtube_title=post.youtube_title,
        youtube_description=post.youtube_description,
        thumbnail_url=post.thumbnail_url,
        status=post.status,  # type: ignore[arg-type]
        scheduled_at=post.scheduled_at,
        created_by=post.created_by,
        approved_by=post.approved_by,
        created_at=post.created_at,
        targets=[
            SocialTargetRead(
                id=target.id,
                account_id=account.id,
                platform=account.platform,  # type: ignore[arg-type]
                account_name=account.name,
                status=target.status,  # type: ignore[arg-type]
                external_url=target.external_url,
                error=target.error,
                posted_at=target.posted_at,
                views=target.views,
                reach=target.reach,
                likes=target.likes,
                comments=target.comments,
                shares=target.shares,
                saves=target.saves,
                avg_watch_ms=target.avg_watch_ms,
                metrics_at=target.metrics_at,
            )
            for target, account in targets
        ],
    )


async def _preview(post: SocialPost) -> str | None:
    """A link to watch the post's reel. None when there is none, or storage is down
    (the queue still shows without it)."""
    if not post.video_key:
        return None
    try:
        return await videos.link(post.video_key)
    except Exception:
        logger.warning("No preview link for post=%s", post.id, exc_info=True)
        return None


async def _read(db: AsyncSession, post: SocialPost) -> SocialPostRead:
    await db.flush()
    await db.refresh(post)
    targets = await repository.targets_of(db, [post.id])
    return _post_read(post, targets.get(post.id, []), await _preview(post))


_VIEWS: dict[str, tuple[str, ...] | None] = {
    "all": None,
    "queue": repository.QUEUE_STATUSES,
    "posted": repository.POSTED_STATUSES,
}


async def list_posts(
    db: AsyncSession, *, cursor: str | None, limit: int, view: PostView = "all"
) -> Page[SocialPostRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_posts(db, after=after, limit=limit + 1, statuses=_VIEWS[view])
    has_more = len(rows) > limit
    rows = rows[:limit]
    targets = await repository.targets_of(db, [row.id for row in rows])
    previews = await asyncio.gather(*(_preview(row) for row in rows))
    return Page(
        items=[
            _post_read(row, targets.get(row.id, []), preview)
            for row, preview in zip(rows, previews, strict=True)
        ],
        next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None,
    )


async def _get_post(db: AsyncSession, post_id: uuid.UUID) -> SocialPost:
    post = await repository.get_post(db, post_id)
    if post is None:
        raise NotFoundError("That post was not found.")
    return post


async def _accounts_for(db: AsyncSession, ids: list[uuid.UUID]) -> list[SocialAccount]:
    unique = list(dict.fromkeys(ids))
    accounts = await repository.get_accounts(db, unique)
    if len(accounts) != len(unique):
        raise ValidationFailedError("One of the chosen accounts is no longer connected.")
    return accounts


def check_fits(
    text: str,
    image_url: str | None,
    platforms: set[str],
    *,
    video_key: str | None = None,
    youtube_title: str | None = None,
) -> None:
    """Refuses a post that a chosen platform would refuse, before it is queued."""
    for platform in sorted(platforms):
        limit = TEXT_LIMITS[platform]
        if len(text) > limit:
            raise ValidationFailedError(
                f"{PLATFORM_NAMES[platform]} allows {limit} characters; this post has {len(text)}."
            )
    if image_url and video_key:
        raise ValidationFailedError("Choose an image or a video, not both.")
    if "instagram" in platforms and not (image_url or video_key):
        raise ValidationFailedError(
            "Instagram needs an image or a video. Add one, or untick Instagram."
        )
    if "youtube" in platforms:
        if not video_key:
            raise ValidationFailedError("YouTube needs a video. Upload a reel, or untick YouTube.")
        if not youtube_title:
            raise ValidationFailedError("Give the YouTube video a title.")
    if "linkedin" in platforms and video_key:
        raise ValidationFailedError(
            "Posting videos to LinkedIn is not supported yet. Untick LinkedIn for reels."
        )


def _check_post(post: SocialPost | SocialPostWrite, platforms: set[str]) -> None:
    check_fits(
        post.text,
        post.image_url,
        platforms,
        video_key=post.video_key,
        youtube_title=post.youtube_title,
    )


async def create_post(
    db: AsyncSession, *, admin: Admin, payload: SocialPostWrite
) -> SocialPostRead:
    accounts = await _accounts_for(db, payload.account_ids)
    _check_post(payload, {account.platform for account in accounts})
    post = SocialPost(
        id=uuid.uuid4(),
        text=payload.text,
        image_url=payload.image_url,
        video_key=payload.video_key,
        youtube_title=payload.youtube_title,
        youtube_description=payload.youtube_description,
        thumbnail_url=payload.thumbnail_url,
        status="draft",
        created_by=admin.email,
    )
    db.add(post)
    await db.flush()
    await repository.replace_targets(db, post.id, [account.id for account in accounts])
    return await _read(db, post)


async def update_post(
    db: AsyncSession, *, admin: Admin, post_id: uuid.UUID, payload: SocialPostWrite
) -> SocialPostRead:
    post = await _get_post(db, post_id)
    if post.status not in _EDITABLE:
        raise ConflictError("Only a draft or a scheduled post can be edited.")
    accounts = await _accounts_for(db, payload.account_ids)
    _check_post(payload, {account.platform for account in accounts})
    old_video = post.video_key
    post.text, post.image_url = payload.text, payload.image_url
    post.video_key = payload.video_key
    post.youtube_title, post.youtube_description = (
        payload.youtube_title,
        payload.youtube_description,
    )
    post.thumbnail_url = payload.thumbnail_url
    if old_video and old_video != post.video_key:
        await _forget_video(old_video)
    await repository.replace_targets(db, post.id, [account.id for account in accounts])
    return await _read(db, post)


async def schedule(
    db: AsyncSession, *, admin: Admin, post_id: uuid.UUID, at: datetime | None
) -> SocialPostRead:
    """Approves a draft to go out at `at`, or now. A scheduled post gets its new time."""
    post = await _get_post(db, post_id)
    if post.status not in _EDITABLE:
        raise ConflictError("Only a draft or a scheduled post can be scheduled.")
    targets = (await repository.targets_of(db, [post.id])).get(post.id, [])
    if not targets:
        raise ValidationFailedError("Choose at least one account to post to.")
    expired = [account.name for _, account in targets if account.status != "active"]
    if expired:
        raise ValidationFailedError(
            f"Reconnect {', '.join(expired)} first: the platform no longer accepts its login."
        )
    _check_post(post, {account.platform for _, account in targets})
    now = datetime.now(UTC)
    if at is not None and at.tzinfo is None:
        raise ValidationFailedError("The time must include a timezone.")
    post.scheduled_at = max(at, now) if at else now
    post.status = "scheduled"
    post.approved_by = admin.email
    return await _read(db, post)


async def unschedule(db: AsyncSession, *, admin: Admin, post_id: uuid.UUID) -> SocialPostRead:
    post = await _get_post(db, post_id)
    if post.status != "scheduled":
        raise ConflictError("Only a scheduled post can be moved back to drafts.")
    post.status, post.scheduled_at, post.approved_by = "draft", None, None
    return await _read(db, post)


async def retry(db: AsyncSession, *, admin: Admin, post_id: uuid.UUID) -> SocialPostRead:
    """Sends the post again to the accounts where it failed. Never to ones where it is up."""
    post = await _get_post(db, post_id)
    if post.status not in ("failed", "partly_posted"):
        raise ConflictError("Only a post that failed somewhere can be retried.")
    targets = (await repository.targets_of(db, [post.id])).get(post.id, [])
    failed = [target for target, _ in targets if target.status == "failed"]
    if not failed:
        raise ConflictError("Nothing failed on this post.")
    for target in failed:
        target.status, target.error, target.attempts = "pending", None, 0
    post.status, post.scheduled_at, post.approved_by = "scheduled", datetime.now(UTC), admin.email
    return await _read(db, post)


async def delete_post(db: AsyncSession, *, admin: Admin, post_id: uuid.UUID) -> None:
    """Removes the post from the queue. A post already up stays on the platform."""
    post = await _get_post(db, post_id)
    if post.status == "publishing":
        raise ConflictError("This post is being published right now. Try again in a minute.")
    video_key = post.video_key
    await db.delete(post)
    if video_key:
        await _forget_video(video_key)


async def _forget_video(key: str) -> None:
    """Removes a reel no post uses any more. Best effort: a leftover file only costs storage."""
    with contextlib.suppress(Exception):
        await videos.delete(key)


async def stats(db: AsyncSession, *, days: int) -> SocialStats:
    since = datetime.now(UTC) - timedelta(days=days)
    return SocialStats(
        days=days,
        platforms=[
            PlatformTotals.model_validate(row)
            for row in await repository.totals_by_platform(db, since)
        ],
        accounts=[_account_read(account) for account in await repository.list_accounts(db)],
        refreshed_at=await repository.last_measured(db),
    )


# --- the dashboard and the stats table ----------------------------------------------

DAY = timedelta(hours=24)
# Readings are taken every 6 hours, so two days back always holds the one from 24h ago.
_HISTORY = timedelta(hours=48)
# Posts the dashboard adds up: far more than will exist for a long time.
_ALL_POSTS = 2000


def title_of(post: SocialPost) -> str:
    return post.youtube_title or (post.text.strip().splitlines() or [""])[0][:120]


def views_gained(
    current: int | None,
    posted_at: datetime | None,
    readings: list[SocialMetricSnapshot],
    cutoff: datetime,
) -> int:
    """Views gained since `cutoff`: now, minus the last reading at or before it. A post
    that went up after `cutoff` gained all of its views since then."""
    if current is None:
        return 0
    before = [r for r in readings if r.taken_at <= cutoff and r.views is not None]
    if before:
        return max(0, current - (before[-1].views or 0))
    if posted_at is not None and posted_at >= cutoff:
        return current
    # Measured only after the cutoff: count from the first reading we have.
    after = [r for r in readings if r.views is not None]
    return max(0, current - (after[0].views or 0)) if after else 0


def since_last_reading(readings: list[SocialMetricSnapshot]) -> int | None:
    measured = [r for r in readings if r.views is not None]
    if len(measured) < 2:
        return None
    return (measured[-1].views or 0) - (measured[-2].views or 0)


async def dashboard(db: AsyncSession) -> SocialDashboard:
    now = datetime.now(UTC)
    cutoff = now - DAY
    rows = await repository.posted_targets(db, _ALL_POSTS)
    history = await repository.snapshots_since(db, [t.id for _, t, _ in rows], now - _HISTORY)

    views: dict[str, int] = {}
    gained: dict[str, int] = {}
    likes = comments = 0
    first_posted: dict[uuid.UUID, datetime] = {}
    for post, target, account in rows:
        platform = account.platform
        views[platform] = views.get(platform, 0) + (target.views or 0)
        gained[platform] = gained.get(platform, 0) + views_gained(
            target.views, target.posted_at, history.get(target.id, []), cutoff
        )
        likes += target.likes or 0
        comments += target.comments or 0
        if target.posted_at and (
            post.id not in first_posted or target.posted_at < first_posted[post.id]
        ):
            first_posted[post.id] = target.posted_at

    queue = await repository.queued(db)
    upcoming = queue[0] if queue else None
    return SocialDashboard(
        total_views=sum(views.values()),
        views_24h=sum(gained.values()),
        platforms=[
            PlatformViews(platform=p, views=views[p], views_24h=gained[p])  # type: ignore[arg-type]
            for p in sorted(views)
        ],
        likes=likes,
        comments=comments,
        posted_24h=sum(1 for at in first_posted.values() if at >= cutoff),
        posted_total=len({post.id for post, _, _ in rows}),
        queued=len(queue),
        next_post=(
            NextPost(id=upcoming.id, title=title_of(upcoming), scheduled_at=upcoming.scheduled_at)
            if upcoming and upcoming.scheduled_at
            else None
        ),
        refreshed_at=await repository.last_measured(db),
    )


async def reel_stats(db: AsyncSession, *, limit: int) -> list[ReelStats]:
    """The newest `limit` posted reels and posts, most viewed first."""
    rows = await repository.posted_targets(db, limit)
    history = await repository.snapshots_since(
        db, [t.id for _, t, _ in rows], datetime.now(UTC) - _HISTORY
    )
    grouped: dict[uuid.UUID, list[tuple[SocialPost, Any, SocialAccount]]] = {}
    for row in rows:
        grouped.setdefault(row[0].id, []).append(row)

    reels: list[ReelStats] = []
    for entries in grouped.values():
        post = entries[0][0]
        targets = [target for _, target, _ in entries]
        since = [since_last_reading(history.get(t.id, [])) for t in targets]
        watched = [t.avg_watch_ms for t in targets if t.avg_watch_ms is not None]
        posted = [t.posted_at for t in targets if t.posted_at]
        reels.append(
            ReelStats(
                id=post.id,
                title=title_of(post),
                thumbnail_url=post.thumbnail_url,
                image_url=post.image_url,
                views=sum(t.views or 0 for t in targets),
                views_by_platform={account.platform: t.views for _, t, account in entries},
                likes=sum(t.likes or 0 for t in targets),
                comments=sum(t.comments or 0 for t in targets),
                shares=sum(t.shares or 0 for t in targets),
                avg_watch_ms=watched[0] if watched else None,
                views_since_refresh=(
                    sum(n for n in since if n is not None)
                    if any(n is not None for n in since)
                    else None
                ),
                posted_at=min(posted) if posted else None,
                links=[
                    PlatformLink(platform=account.platform, url=t.external_url)  # type: ignore[arg-type]
                    for _, t, account in entries
                ],
            )
        )
    reels.sort(key=lambda reel: reel.views, reverse=True)
    return reels
