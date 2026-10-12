import logging
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.inbox import gmail, service
from backend.modules.inbox.schemas import (
    ConnectUrl,
    EmailRead,
    InboxInsights,
    InboxStatus,
    InterviewRead,
    InterviewUpdate,
    ReviewAction,
)
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("/status", response_model=InboxStatus)
async def read_inbox_status(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> InboxStatus:
    return await service.get_status(db, user_id=user.id)


@router.get("/gmail/connect-url", response_model=ConnectUrl)
async def read_gmail_connect_url(user: User = Depends(get_db_user)) -> ConnectUrl:
    """Where to send the browser so the user can grant read-only access."""
    return ConnectUrl(url=service.connect_url(user.id))


@router.get("/gmail/callback", include_in_schema=False)
async def gmail_callback(
    background_tasks: BackgroundTasks,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Google sends the browser here after the consent screen. There is no
    login header on this request; the user is identified by the encrypted
    `state` we issued. The browser is always sent back to Settings with the
    outcome, never shown a raw error.
    """
    back = f"{get_settings().dashboard_url}/app/settings?gmail="
    if error or not code or not state:
        return RedirectResponse(f"{back}denied")
    try:
        user_id = await service.finish_connecting(db, code=code, state=state)
    except service.InvalidConnectStateError:
        return RedirectResponse(f"{back}expired")
    except gmail.GmailApiOffError:
        logger.warning("Connecting Gmail failed: the Gmail API is not enabled for this project")
        return RedirectResponse(f"{back}api_off")
    except (gmail.GmailAccessLostError, gmail.GmailNotConfiguredError) as exc:
        # Google's own explanation, kept in the server log (it holds no token).
        logger.warning("Connecting Gmail failed: %s", exc)
        return RedirectResponse(f"{back}denied")
    except Exception:
        logger.exception("Connecting Gmail failed")
        return RedirectResponse(f"{back}failed")

    await service.start_sync(db, user_id=user_id)
    await db.commit()  # the background reader must see the new connection
    background_tasks.add_task(service.run_sync, user_id)
    return RedirectResponse(f"{back}connected")


@router.delete("/gmail", status_code=204)
async def disconnect_gmail(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.disconnect(db, user_id=user.id)


@router.post("/sync", response_model=InboxStatus, status_code=202)
async def sync_inbox(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> InboxStatus:
    """Starts reading the inbox and returns at once. Poll `/inbox/status` until
    `sync_status` is back to "idle".
    """
    await service.start_sync(db, user_id=user.id)
    await db.commit()  # the background reader must see "syncing" when it starts
    background_tasks.add_task(service.run_sync, user.id)
    return await service.get_status(db, user_id=user.id)


@router.get("/messages", response_model=Page[EmailRead])
async def list_inbox_messages(
    state: Literal["linked", "created", "review", "dismissed"] | None = None,
    # Only the mails about one application, for showing them beside it.
    application_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> Page[EmailRead]:
    return await service.list_messages(
        db,
        user_id=user.id,
        state=state,
        application_id=application_id,
        cursor=cursor,
        limit=limit,
    )


@router.patch("/messages/{message_id}", response_model=EmailRead)
async def resolve_inbox_message(
    message_id: uuid.UUID,
    payload: ReviewAction,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> EmailRead:
    return await service.resolve(db, user_id=user.id, message_id=message_id, payload=payload)


@router.get("/insights", response_model=InboxInsights)
async def read_inbox_insights(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> InboxInsights:
    """Patterns across the user's applications: what the jobs that said no
    asked for that their profile did not show.
    """
    return await service.get_insights(db, user_id=user.id)


@router.get("/interviews", response_model=list[InterviewRead])
async def list_interviews(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> list[InterviewRead]:
    """Interviews found in the user's mail, soonest first. Not paginated: a
    person has a handful of these, and the list is capped at 200.
    """
    return await service.list_interviews(db, user_id=user.id)


@router.patch("/interviews/{interview_id}", response_model=InterviewRead)
async def update_interview(
    interview_id: uuid.UUID,
    payload: InterviewUpdate,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewRead:
    """Sets or corrects the time, link or place. A time the user has set is
    never overwritten by a later mail.
    """
    return await service.update_interview(
        db, user_id=user.id, interview_id=interview_id, payload=payload
    )


@router.delete("/interviews/{interview_id}", status_code=204)
async def delete_interview(
    interview_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_interview(db, user_id=user.id, interview_id=interview_id)
