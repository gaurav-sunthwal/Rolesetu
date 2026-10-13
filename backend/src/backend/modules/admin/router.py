import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
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
    ErrorEventRead,
    ErrorSummary,
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


@router.get("/errors", response_model=ErrorSummary)
async def list_errors(
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
    source: Annotated[str | None, Query(max_length=20)] = None,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> ErrorSummary:
    """What went wrong in the period, grouped by problem, most frequent first."""
    return await service.list_errors(db, hours=hours, source=source)


@router.get("/errors/{fingerprint}", response_model=list[ErrorEventRead])
async def read_error(
    fingerprint: Annotated[str, Path(max_length=64)],
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ErrorEventRead]:
    return await service.error_events(db, fingerprint=fingerprint)


@router.delete("/errors/{fingerprint}", status_code=204)
async def clear_error(
    fingerprint: Annotated[str, Path(max_length=64)],
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Removes every event of one problem, once it has been dealt with."""
    await service.clear_errors(db, admin=admin, fingerprint=fingerprint)
