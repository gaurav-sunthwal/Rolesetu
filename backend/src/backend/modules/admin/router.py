import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.admin import service
from backend.modules.admin.dependencies import Admin, get_admin
from backend.modules.admin.schemas import (
    AdminActionRead,
    AdminRead,
    AdminStats,
    AdminUserDetail,
    AdminUserRow,
    WaitlistRow,
)

router = APIRouter(prefix="/admin", tags=["admin"])

Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/me", response_model=AdminRead)
async def read_admin(admin: Admin = Depends(get_admin)) -> AdminRead:
    """Lets the panel find out whether the signed-in account is an admin."""
    return AdminRead(email=admin.email)


@router.get("/stats", response_model=AdminStats)
async def read_stats(
    _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> AdminStats:
    return await service.stats(db)


@router.get("/users", response_model=Page[AdminUserRow])
async def list_users(
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Limit = 25,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminUserRow]:
    return await service.list_users(db, search=q, cursor=cursor, limit=limit)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def read_user(
    user_id: uuid.UUID,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    return await service.user_detail(db, admin=admin, user_id=user_id)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    confirm_email: Annotated[str, Query(max_length=320)],
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes the account and everything stored for it. Cannot be undone, so
    the caller must repeat the account's email address.
    """
    await service.delete_user(db, admin=admin, user_id=user_id, confirm_email=confirm_email)


@router.get("/waitlist", response_model=Page[WaitlistRow])
async def list_waitlist(
    cursor: str | None = None,
    limit: Limit = 50,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[WaitlistRow]:
    return await service.list_waitlist(db, admin=admin, cursor=cursor, limit=limit)


@router.get("/audit", response_model=Page[AdminActionRead])
async def list_audit(
    cursor: str | None = None,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminActionRead]:
    return await service.list_actions(db, cursor=cursor, limit=limit)
