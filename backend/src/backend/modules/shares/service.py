"""Public match cards: a user shares one of their scores behind a short link.

Sharing is always the user's own choice, per match, and can be undone. The
card copies only the job, the score and skill names, never resume content.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ConflictError, NotFoundError, RateLimitedError
from backend.modules.matches import repository as matches_repository
from backend.modules.matches.models import Match
from backend.modules.shares import repository
from backend.modules.shares.models import MatchShare
from backend.modules.shares.schemas import ShareRead

MAX_SHARES_PER_HOUR = 30
MAX_MATCHED = 8
MAX_GAPS = 6
_SLUG_BYTES = 7  # 10 URL-safe characters: short to paste, too many to guess


def matched_skills(skill_results: list[dict[str, Any]]) -> list[str]:
    """The skills the user showed, strongest and required first."""

    def rank(skill: dict[str, Any]) -> tuple[int, int]:
        return (0 if skill.get("required") else 1, 0 if skill.get("verdict") == "strong" else 1)

    shown = [skill for skill in skill_results if skill.get("verdict") in ("strong", "partial")]
    names: list[str] = []
    for skill in sorted(shown, key=rank):
        name = str(skill.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    return names[:MAX_MATCHED]


def to_read(share: MatchShare) -> ShareRead:
    return ShareRead(
        slug=share.slug,
        role=share.role,
        company=share.company,
        score=share.score,
        matched=share.matched,
        gaps=share.gaps,
        created_at=share.created_at,
    )


def _fill(share: MatchShare, match: Match, show_gaps: bool) -> None:
    role, company = match.job.role, match.job.company
    share.role = role[:160] if role else None
    share.company = company[:160] if company else None
    share.score = match.score or 0
    share.matched = matched_skills(match.skill_results)
    share.gaps = [gap for gap in match.gaps if gap][:MAX_GAPS] if show_gaps else []


async def share_match(
    db: AsyncSession, *, user_id: uuid.UUID, match_id: uuid.UUID, show_gaps: bool
) -> ShareRead:
    """Makes the match's card public, or refreshes the card it already has.
    Asking twice gives the same link, so a double click never makes two.
    """
    match = await matches_repository.get(db, user_id, match_id)
    if match is None:
        raise NotFoundError("That job check was not found.")
    if match.status != "completed" or match.score is None:
        raise ConflictError("This job check has not finished yet. Share it once it has a score.")

    share = await repository.get_for_match(db, user_id, match_id)
    if share is None:
        since = datetime.now(UTC) - timedelta(hours=1)
        if await repository.count_since(db, user_id, since) >= MAX_SHARES_PER_HOUR:
            raise RateLimitedError(
                f"You have shared {MAX_SHARES_PER_HOUR} scores in the last hour. "
                "Please try again later."
            )
        share = MatchShare(
            id=uuid.uuid4(),
            slug=secrets.token_urlsafe(_SLUG_BYTES)[:10],
            user_id=user_id,
            match_id=match_id,
        )
        _fill(share, match, show_gaps)
        try:
            async with db.begin_nested():
                db.add(share)
        except IntegrityError:
            # The same match was shared a moment ago by another request.
            existing = await repository.get_for_match(db, user_id, match_id)
            if existing is None:
                raise
            share = existing
            _fill(share, match, show_gaps)
    else:
        _fill(share, match, show_gaps)
    await db.flush()
    await db.refresh(share)
    return to_read(share)


async def stop_sharing(db: AsyncSession, *, user_id: uuid.UUID, slug: str) -> None:
    if not await repository.delete_owned(db, user_id, slug):
        raise NotFoundError("That shared link was not found.")


async def public_share(db: AsyncSession, slug: str) -> ShareRead:
    share = await repository.get_by_slug(db, slug)
    if share is None:
        raise NotFoundError("This shared score was removed or never existed.")
    return to_read(share)
