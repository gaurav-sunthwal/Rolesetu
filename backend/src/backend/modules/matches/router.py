import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.matches import service
from backend.modules.matches.schemas import MatchCreate, MatchRead
from backend.modules.users.dependencies import get_db_user, get_db_user_or_extension
from backend.modules.users.models import User

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchRead, status_code=202)
async def create_match(
    payload: MatchCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> MatchRead:
    """Scoring takes several seconds, so this returns straight away with a
    pending match; the client polls GET /matches/{id} until it completes.
    """
    match, needs_scoring = await service.start_match(db, user_id=user.id, payload=payload)
    if needs_scoring:
        # Commit first: the runner opens its own session and must see the row.
        await db.commit()
        background_tasks.add_task(service.run_match, match.id)
    return match


@router.get("", response_model=Page[MatchRead])
async def list_matches(
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> Page[MatchRead]:
    return await service.list_matches(db, user_id=user.id, cursor=cursor, limit=limit)


@router.get("/{match_id}", response_model=MatchRead)
async def read_match(
    match_id: uuid.UUID,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> MatchRead:
    return await service.get_match(db, user_id=user.id, match_id=match_id)
