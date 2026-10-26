import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.shares import service
from backend.modules.shares.schemas import ShareCreate, ShareRead
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(tags=["shares"])

Slug = Annotated[str, Path(min_length=4, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")]


@router.post("/matches/{match_id}/share", response_model=ShareRead)
async def share_match(
    match_id: uuid.UUID,
    payload: ShareCreate,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ShareRead:
    """Makes this match's score card public. Asking again returns the same link."""
    return await service.share_match(
        db, user_id=user.id, match_id=match_id, show_gaps=payload.show_gaps
    )


@router.delete("/shares/{slug}", status_code=204)
async def stop_sharing(
    slug: Slug, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.stop_sharing(db, user_id=user.id, slug=slug)


@router.get("/public/shares/{slug}", response_model=ShareRead)
async def read_public_share(slug: Slug, db: AsyncSession = Depends(get_db)) -> ShareRead:
    """A shared score card. Works without signing in: the link is the permission."""
    return await service.public_share(db, slug)
