import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.admin.dependencies import Admin, get_admin
from backend.modules.social import images, service
from backend.modules.social.platforms.base import PostRejectedError
from backend.modules.social.schemas import (
    ConnectUrl,
    ImageUploaded,
    Provider,
    ScheduleRequest,
    SocialOverview,
    SocialPostRead,
    SocialPostWrite,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["social"])
admin_router = APIRouter(prefix="/admin/social", tags=["social"])

Limit = Annotated[int, Query(ge=1, le=100)]


@admin_router.get("", response_model=SocialOverview)
async def read_overview(
    _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> SocialOverview:
    """Which platforms are set up on the server, and the accounts connected."""
    return await service.overview(db)


@admin_router.get("/{provider}/connect-url", response_model=ConnectUrl)
async def read_connect_url(provider: Provider, admin: Admin = Depends(get_admin)) -> ConnectUrl:
    return ConnectUrl(url=service.connect_url(admin, provider))


@admin_router.get("/{provider}/callback", include_in_schema=False)
async def connect_callback(
    provider: Provider,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """The platform sends the browser here after its consent screen, without
    our login header: the admin is known from the encrypted `state`. The
    browser always goes back to the Social page with the outcome.
    """
    back = f"{get_settings().admin_url.rstrip('/')}/social?provider={provider}&result="
    if error or not code or not state:
        return RedirectResponse(f"{back}denied")
    try:
        count = await service.finish_connecting(db, provider=provider, code=code, state=state)
    except service.InvalidConnectStateError:
        return RedirectResponse(f"{back}expired")
    except PostRejectedError as exc:
        # The platform's explanation stays in the log (it holds no token).
        logger.warning("Connecting %s failed: %s", provider, exc)
        return RedirectResponse(f"{back}refused")
    except Exception:
        logger.exception("Connecting %s failed", provider)
        return RedirectResponse(f"{back}failed")
    return RedirectResponse(f"{back}{'connected' if count else 'none'}")


@admin_router.delete("/accounts/{account_id}", status_code=204)
async def disconnect_account(
    account_id: uuid.UUID, admin: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> None:
    await service.disconnect(db, admin=admin, account_id=account_id)


@admin_router.post("/images", response_model=ImageUploaded)
async def upload_image(file: UploadFile, _: Admin = Depends(get_admin)) -> ImageUploaded:
    """Stores an image for a post. Returns its public link, made a JPEG."""
    data = await file.read(images.MAX_UPLOAD_BYTES + 1)
    return ImageUploaded(url=await service.upload_image(data))


@admin_router.get("/posts", response_model=Page[SocialPostRead])
async def list_posts(
    cursor: str | None = None,
    limit: Limit = 25,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[SocialPostRead]:
    return await service.list_posts(db, cursor=cursor, limit=limit)


@admin_router.post("/posts", response_model=SocialPostRead, status_code=201)
async def create_post(
    payload: SocialPostWrite, admin: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> SocialPostRead:
    """Saves a draft. Nothing is posted until the draft is scheduled."""
    return await service.create_post(db, admin=admin, payload=payload)


@admin_router.put("/posts/{post_id}", response_model=SocialPostRead)
async def update_post(
    post_id: uuid.UUID,
    payload: SocialPostWrite,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> SocialPostRead:
    return await service.update_post(db, admin=admin, post_id=post_id, payload=payload)


@admin_router.post("/posts/{post_id}/schedule", response_model=SocialPostRead)
async def schedule_post(
    post_id: uuid.UUID,
    payload: ScheduleRequest,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> SocialPostRead:
    """Approves a draft to go out at the given time, or within a minute."""
    return await service.schedule(db, admin=admin, post_id=post_id, at=payload.at)


@admin_router.post("/posts/{post_id}/unschedule", response_model=SocialPostRead)
async def unschedule_post(
    post_id: uuid.UUID, admin: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> SocialPostRead:
    return await service.unschedule(db, admin=admin, post_id=post_id)


@admin_router.post("/posts/{post_id}/retry", response_model=SocialPostRead)
async def retry_post(
    post_id: uuid.UUID, admin: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> SocialPostRead:
    return await service.retry(db, admin=admin, post_id=post_id)


@admin_router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: uuid.UUID, admin: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> None:
    await service.delete_post(db, admin=admin, post_id=post_id)


@router.get("/public/social-images/{name}", include_in_schema=False)
async def read_image(name: str) -> Response:
    """A post's image, public so Facebook and Instagram can download it."""
    return Response(
        content=await images.read(name),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


router.include_router(admin_router)
