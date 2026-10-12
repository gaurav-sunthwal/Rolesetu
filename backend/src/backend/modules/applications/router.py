import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.applications import service
from backend.modules.applications.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationRead,
    ApplicationStats,
    ApplicationStatus,
    ApplicationUpdate,
)
from backend.modules.users.dependencies import get_db_user, get_db_user_or_extension
from backend.modules.users.models import User

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=Page[ApplicationRead])
async def list_applications(
    status: ApplicationStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> Page[ApplicationRead]:
    return await service.list_applications(
        db, user_id=user.id, status=status, search=q or None, cursor=cursor, limit=limit
    )


@router.get("/stats", response_model=ApplicationStats)
async def read_stats(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ApplicationStats:
    return await service.get_stats(db, user_id=user.id)


@router.post("", response_model=ApplicationDetail, status_code=201)
async def create_application(
    payload: ApplicationCreate,
    idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> ApplicationDetail:
    return await service.create_application(
        db, user_id=user.id, payload=payload, idempotency_key=idempotency_key
    )


@router.get("/{application_id}", response_model=ApplicationDetail)
async def read_application(
    application_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationDetail:
    return await service.get_application(db, user_id=user.id, application_id=application_id)


@router.patch("/{application_id}", response_model=ApplicationDetail)
async def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> ApplicationDetail:
    return await service.update_application(
        db, user_id=user.id, application_id=application_id, payload=payload
    )


@router.delete("/{application_id}", status_code=204)
async def delete_application(
    application_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_application(db, user_id=user.id, application_id=application_id)
