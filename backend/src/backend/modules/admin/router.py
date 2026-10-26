import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.admin import service
from backend.modules.admin.dependencies import Admin, get_admin
from backend.modules.admin.schemas import (
    AccountDeleted,
    AdminActionRead,
    AdminRead,
    AdminStats,
    AdminUserDetail,
    AdminUserRow,
    BulkQueued,
    EmailCompose,
    EmailDefaults,
    EmailTemplate,
    ErrorEventRead,
    ErrorSummary,
    OutreachRead,
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
    extension: Literal["missing"] | None = None,
    cursor: str | None = None,
    limit: Limit = 25,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminUserRow]:
    return await service.list_users(
        db, search=q, extension_missing=extension == "missing", cursor=cursor, limit=limit
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def read_user(
    user_id: uuid.UUID,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    return await service.user_detail(db, admin=admin, user_id=user_id)


@router.get(
    "/users/{user_id}/resumes/{resume_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def read_resume_file(
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The resume PDF, served through the API (not a storage link) so the panel
    can draw it in the page. Recorded in the audit log each time.
    """
    data, filename = await service.resume_file(
        db, admin=admin, user_id=user_id, resume_id=resume_id
    )
    # Headers carry plain ASCII only; a name with other letters loses them here.
    safe_name = filename.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            # A resume must not be kept in any shared cache.
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/users/{user_id}", response_model=AccountDeleted)
async def delete_user(
    user_id: uuid.UUID,
    confirm_email: Annotated[str, Query(max_length=320)],
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> AccountDeleted:
    """Deletes the account, everything stored for it, and its Firebase sign-in.
    Cannot be undone, so the caller must repeat the account's email address.
    """
    firebase_uid = await service.delete_user(
        db, admin=admin, user_id=user_id, confirm_email=confirm_email
    )
    # The data is deleted for good before the sign-in is touched.
    await db.commit()
    return await service.remove_sign_in(firebase_uid)


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


@router.get("/emails/extension-nudge", response_model=EmailDefaults)
async def read_email_defaults(
    _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> EmailDefaults:
    """The suggested email to people without the extension, and how many it would reach."""
    return await service.email_defaults(db)


@router.get("/users/{user_id}/email-templates", response_model=list[EmailTemplate])
async def read_email_templates(
    user_id: uuid.UUID, _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> list[EmailTemplate]:
    """Ready-made notes for this person, filled in with what they have done."""
    return await service.email_templates(db, user_id)


@router.post("/users/{user_id}/email", response_model=OutreachRead)
async def email_user(
    user_id: uuid.UUID,
    payload: EmailCompose,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> OutreachRead:
    """Sends one email to one person now. The answer says whether it went."""
    return await service.email_user(
        db,
        admin=admin,
        user_id=user_id,
        subject=payload.subject,
        message=payload.message,
        kind=payload.kind,
    )


@router.post("/emails/extension-nudge", response_model=BulkQueued)
async def email_everyone_without_extension(
    payload: EmailCompose,
    background_tasks: BackgroundTasks,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> BulkQueued:
    """Writes to everyone without the extension, in the background, up to a limit."""
    queued = await service.start_extension_nudges(
        db, admin=admin, subject=payload.subject, message=payload.message
    )
    if queued:
        # Committed first, so the audit entry exists even if sending is cut short.
        await db.commit()
        background_tasks.add_task(
            service.send_extension_nudges, admin.email, payload.subject, payload.message
        )
    return BulkQueued(queued=queued)
