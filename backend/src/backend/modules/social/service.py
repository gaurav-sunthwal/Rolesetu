"""The admin panel's Social section: connecting accounts and managing the queue.

A post is a draft until an admin schedules it. Scheduling is the approval:
nothing reaches a platform without it. The publisher (publisher.py) sends
scheduled posts when their time comes.
"""

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.encryption import decrypt_text, encrypt_text
from backend.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.modules.admin.dependencies import Admin
from backend.modules.social import images, repository
from backend.modules.social.models import SocialAccount, SocialPost
from backend.modules.social.platforms import linkedin, meta
from backend.modules.social.schemas import (
    Provider,
    ProviderStatus,
    SocialAccountRead,
    SocialOverview,
    SocialPostRead,
    SocialPostWrite,
    SocialTargetRead,
)

STATE_VALID_SECONDS = 600
TEXT_LIMITS: dict[str, int] = {
    "linkedin": linkedin.MAX_TEXT,
    "facebook": meta.MAX_FACEBOOK_TEXT,
    "instagram": meta.MAX_INSTAGRAM_TEXT,
}
PLATFORM_NAMES: dict[str, str] = {
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "instagram": "Instagram",
}


class InvalidConnectStateError(Exception):
    """The callback's `state` is missing, forged, too old or for someone no longer an admin."""


def _account_read(account: SocialAccount) -> SocialAccountRead:
    return SocialAccountRead(
        id=account.id,
        platform=account.platform,  # type: ignore[arg-type]
        name=account.name,
        status=account.status,  # type: ignore[arg-type]
        expires_at=account.expires_at,
        connected_by=account.connected_by,
        created_at=account.created_at,
    )


async def overview(db: AsyncSession) -> SocialOverview:
    return SocialOverview(
        providers=[
            ProviderStatus(provider="linkedin", configured=linkedin.is_configured()),
            ProviderStatus(provider="meta", configured=meta.is_configured()),
        ],
        accounts=[_account_read(account) for account in await repository.list_accounts(db)],
    )


def connect_url(admin: Admin, provider: Provider) -> str:
    """The platform's consent page. `state` carries which admin asked, encrypted,
    because the callback arrives without our login header.
    """
    state = encrypt_text(f"{provider}|{admin.email}|{int(time.time())}")
    return linkedin.consent_url(state) if provider == "linkedin" else meta.consent_url(state)


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


def _post_read(post: SocialPost, targets: list[repository.TargetRow]) -> SocialPostRead:
    return SocialPostRead(
        id=post.id,
        text=post.text,
        image_url=post.image_url,
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
            )
            for target, account in targets
        ],
    )


async def _read(db: AsyncSession, post: SocialPost) -> SocialPostRead:
    await db.flush()
    await db.refresh(post)
    targets = await repository.targets_of(db, [post.id])
    return _post_read(post, targets.get(post.id, []))


async def list_posts(db: AsyncSession, *, cursor: str | None, limit: int) -> Page[SocialPostRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_posts(db, after=after, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    targets = await repository.targets_of(db, [row.id for row in rows])
    return Page(
        items=[_post_read(row, targets.get(row.id, [])) for row in rows],
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


def check_fits(text: str, image_url: str | None, platforms: set[str]) -> None:
    """Refuses a post that a chosen platform would refuse, before it is queued."""
    for platform in sorted(platforms):
        limit = TEXT_LIMITS[platform]
        if len(text) > limit:
            raise ValidationFailedError(
                f"{PLATFORM_NAMES[platform]} allows {limit} characters; this post has {len(text)}."
            )
    if "instagram" in platforms and not image_url:
        raise ValidationFailedError("Instagram needs an image. Add one, or untick Instagram.")


async def create_post(
    db: AsyncSession, *, admin: Admin, payload: SocialPostWrite
) -> SocialPostRead:
    accounts = await _accounts_for(db, payload.account_ids)
    check_fits(payload.text, payload.image_url, {account.platform for account in accounts})
    post = SocialPost(
        id=uuid.uuid4(),
        text=payload.text,
        image_url=payload.image_url,
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
    if post.status != "draft":
        raise ConflictError("Only drafts can be edited. Unschedule the post first.")
    accounts = await _accounts_for(db, payload.account_ids)
    check_fits(payload.text, payload.image_url, {account.platform for account in accounts})
    post.text, post.image_url = payload.text, payload.image_url
    await repository.replace_targets(db, post.id, [account.id for account in accounts])
    return await _read(db, post)


async def schedule(
    db: AsyncSession, *, admin: Admin, post_id: uuid.UUID, at: datetime | None
) -> SocialPostRead:
    """Approves a draft to go out at `at`, or now."""
    post = await _get_post(db, post_id)
    if post.status != "draft":
        raise ConflictError("Only drafts can be scheduled.")
    targets = (await repository.targets_of(db, [post.id])).get(post.id, [])
    if not targets:
        raise ValidationFailedError("Choose at least one account to post to.")
    expired = [account.name for _, account in targets if account.status != "active"]
    if expired:
        raise ValidationFailedError(
            f"Reconnect {', '.join(expired)} first: the platform no longer accepts its login."
        )
    check_fits(post.text, post.image_url, {account.platform for _, account in targets})
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
    await db.delete(post)
