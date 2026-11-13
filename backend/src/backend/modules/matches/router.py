import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.pagination import Page
from backend.core.security import CurrentUser, get_current_user
from backend.db.session import get_db
from backend.modules.ai_calls.service import Source
from backend.modules.matches import service
from backend.modules.matches.schemas import MatchCreate, MatchRead
from backend.modules.users.dependencies import get_db_user, get_db_user_or_extension
from backend.modules.users.models import User

router = APIRouter(prefix="/matches", tags=["matches"])


# How long a client that cannot poll is kept waiting for a model-read job.
# Under the 25 seconds the extension gives a request before it gives up.
WAIT_FOR_RESULT_SECONDS = 20
# Runs that outlive the request that started them, kept so they are not
# garbage-collected half way through.
_running: set[asyncio.Task[None]] = set()


@router.post("", response_model=MatchRead, status_code=202)
async def create_match(
    payload: MatchCreate,
    background_tasks: BackgroundTasks,
    response: Response,
    user: User = Depends(get_db_user_or_extension),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    prefer: Annotated[str | None, Header()] = None,
) -> MatchRead:
    """Jobs are scored in the request by the local engine. Only with the model
    engine (`match_engine = "llm"`) does a check take several seconds, and then
    how that is handled depends on the client:

    - one that sends `Prefer: respond-async` (RFC 7240) gets the pending match
      at once and polls GET /matches/{id} until it completes;
    - any other (an older extension that cannot poll) is kept waiting up to
      WAIT_FOR_RESULT_SECONDS for the finished result, and gets it pending only
      if it takes longer.
    """
    source: Source = "extension" if current_user.via_extension else "dashboard"
    started = await service.start_match(
        db,
        user_id=user.id,
        payload=payload,
        paid_reads=True if payload.jd_text is None else not current_user.via_extension,
        source=source,
    )
    match = started.match
    if started.save is not None:
        # Scored here: answer now, write it down just after the answer is sent.
        background_tasks.add_task(started.save)
    if not started.needs_model:
        return match
    # Commit first: the runner opens its own session and must see the row.
    await db.commit()
    if prefer is not None and "respond-async" in prefer.lower():
        background_tasks.add_task(service.run_match, match.id, source)
        response.headers["Preference-Applied"] = "respond-async"
        return match

    task = asyncio.create_task(service.run_match(match.id, source))
    _running.add(task)
    task.add_done_callback(_running.discard)
    # Waiting does not cancel the run: past the limit it carries on, and the
    # result is there for the next request.
    await asyncio.wait({task}, timeout=WAIT_FOR_RESULT_SECONDS)
    if not task.done():
        return match
    db.expire_all()
    return await service.get_match(db, user_id=user.id, match_id=match.id)


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
