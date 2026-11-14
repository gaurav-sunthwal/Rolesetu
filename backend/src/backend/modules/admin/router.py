import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.answer_writer import PURPOSE as AI_ANSWER_PURPOSE
from backend.core.pagination import Page
from backend.db.session import get_db
from backend.modules.admin import service
from backend.modules.admin.dependencies import Admin, get_admin
from backend.modules.admin.leaderboard import Leaderboard, leaderboard
from backend.modules.admin.repository import UserFilter
from backend.modules.admin.schemas import (
    AccountDeleted,
    AdminApplicationRow,
    AdminJobCheckRow,
    AdminPreviewRow,
    AdminRead,
    AdminStats,
    AdminUserDetail,
    AdminUserRow,
    AiCallRead,
    AiCallSummary,
    BulkQueued,
    DailyActivity,
    DomainCatalogAdminRead,
    EmailCompose,
    EmailDefaults,
    EmailTemplate,
    ErrorEventRead,
    ErrorSummary,
    OutreachRead,
    WaitlistRow,
)
from backend.modules.billing import admin as billing_admin
from backend.modules.billing.admin_schemas import (
    BillingOverview,
    GrantWrite,
    NoteWrite,
    OrderAdminRead,
    OrderStatus,
    PlanAdminRead,
    PlanWrite,
    UserBillingAdmin,
)
from backend.modules.ext_events import repository as events_repo
from backend.modules.ext_events.schemas import ExtAnalytics, ExtEventRead, ExtEventStats
from backend.modules.ext_installs import repository as installs_repo
from backend.modules.ext_installs.schemas import InstallStats

router = APIRouter(prefix="/admin", tags=["admin"])

Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/me", response_model=AdminRead)
async def read_admin(admin: Admin = Depends(get_admin)) -> AdminRead:
    """Lets the panel find out whether the signed-in account is an admin."""
    return AdminRead(email=admin.email)


@router.get("/leaderboard", response_model=Leaderboard)
async def read_leaderboard(
    days: Annotated[int | None, Query(ge=1, le=3650)] = 30,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Leaderboard:
    """The most active users over the last `days` (all time when left out), each
    with the features they use most."""
    return await leaderboard(db, days=days, limit=limit)


@router.get("/stats", response_model=AdminStats)
async def read_stats(
    _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> AdminStats:
    return await service.stats(db)


@router.get("/users", response_model=Page[AdminUserRow])
async def list_users(
    q: Annotated[str | None, Query(max_length=200)] = None,
    extension: Literal["missing"] | None = None,
    has: UserFilter | None = None,
    joined_on: date | None = None,
    cursor: str | None = None,
    limit: Limit = 25,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminUserRow]:
    """`has` keeps the users a dashboard count is about: with a profile, with
    the extension connected (or used in the last week), or with Gmail connected.
    """
    return await service.list_users(
        db,
        search=q,
        extension_missing=extension == "missing",
        has=has,
        joined_on=joined_on,
        cursor=cursor,
        limit=limit,
    )


@router.get("/job-checks", response_model=Page[AdminJobCheckRow])
async def list_job_checks(
    hours: Annotated[int | None, Query(ge=1, le=8760)] = None,
    day: date | None = None,
    paid: bool = False,
    cursor: str | None = None,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminJobCheckRow]:
    """Everyone's job checks, newest first. `day` (a UTC date) keeps one day's;
    `paid` keeps those read through the paid reader.
    """
    return await service.list_job_checks(
        db, hours=hours, day=day, paid=paid, cursor=cursor, limit=limit
    )


@router.get("/applications", response_model=Page[AdminApplicationRow])
async def list_applications(
    day: date | None = None,
    cursor: str | None = None,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminApplicationRow]:
    """Everyone's tracked applications, newest first. `day` (a UTC date) keeps one day's."""
    return await service.list_applications(db, day=day, cursor=cursor, limit=limit)


@router.get("/daily", response_model=list[DailyActivity])
async def read_daily_activity(
    start: date,
    end: date,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> list[DailyActivity]:
    """Sign-ups, job checks and applications per UTC day, from `start` to `end`."""
    return await service.daily_activity(db, start=start, end=end)


@router.get("/domain-catalogs", response_model=list[DomainCatalogAdminRead])
async def list_domain_catalogs(
    _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> list[DomainCatalogAdminRead]:
    """Skill dictionaries built for fields outside software and data.

    Each field is generated once and then reused. Uploading a resume again
    does not rebuild it.
    """
    from backend.modules.domain_catalogs import repository as catalogs

    rows = await catalogs.list_all(db)
    return [
        DomainCatalogAdminRead(
            field_key=row.field_key,
            version=row.version,
            source=row.source,
            catalog_text=row.catalog_text,
            core_skill_names=list(row.core_skill_names),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/previews", response_model=Page[AdminPreviewRow])
async def list_previews(
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
    host: Annotated[str | None, Query(max_length=200)] = None,
    paid: bool = False,
    failed: bool = False,
    cursor: str | None = None,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminPreviewRow]:
    """Job links pasted on the landing page, newest first. Kept for a day."""
    return await service.list_previews(
        db, hours=hours, host=host, paid=paid, failed=failed, cursor=cursor, limit=limit
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def read_user(
    user_id: uuid.UUID,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    return await service.user_detail(db, user_id=user_id)


@router.get(
    "/users/{user_id}/resumes/{resume_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def read_resume_file(
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The resume PDF, served through the API (not a storage link) so the panel
    can draw it in the page.
    """
    data, filename = await service.resume_file(db, user_id=user_id, resume_id=resume_id)
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
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> AccountDeleted:
    """Deletes the account, everything stored for it, and its Firebase sign-in.
    Cannot be undone, so the caller must repeat the account's email address.
    """
    firebase_uid = await service.delete_user(db, user_id=user_id, confirm_email=confirm_email)
    # The data is deleted for good before the sign-in is touched.
    await db.commit()
    return await service.remove_sign_in(firebase_uid)


@router.get("/waitlist", response_model=Page[WaitlistRow])
async def list_waitlist(
    cursor: str | None = None,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[WaitlistRow]:
    return await service.list_waitlist(db, cursor=cursor, limit=limit)


AiSource = Literal["extension", "dashboard", "resume", "other"]
Hours = Annotated[int, Query(ge=1, le=2160)]


@router.get("/ai-calls/summary", response_model=AiCallSummary)
async def read_ai_call_summary(
    hours: Hours = 24,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> AiCallSummary:
    """How many model calls were made in the period, and from where."""
    return await service.ai_call_summary(db, hours=hours)


@router.get("/ai-calls", response_model=Page[AiCallRead])
async def list_ai_calls(
    hours: Hours = 24,
    source: AiSource | None = None,
    user_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: Limit = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AiCallRead]:
    """Every model call in the period, newest first."""
    return await service.list_ai_calls(
        db, hours=hours, source=source, user_id=user_id, cursor=cursor, limit=limit
    )


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
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Removes every event of one problem, once it has been dealt with."""
    await service.clear_errors(db, fingerprint=fingerprint)


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
        db, subject=payload.subject, message=payload.message
    )
    if queued:
        background_tasks.add_task(
            service.send_extension_nudges, admin.email, payload.subject, payload.message
        )
    return BulkQueued(queued=queued)


@router.get("/ext-events", response_model=ExtEventStats)
async def read_ext_event_stats(
    hours: Hours = 168,  # default: last 7 days
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> ExtEventStats:
    """Extension usage analytics: what users do inside the extension,
    aggregated by event type, day, and site. No personal data is returned.
    """
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(hours=hours)
    t = await events_repo.totals(db, since=since)
    d = await events_repo.daily(db, since=since)
    s = await events_repo.top_sites(db, since=since)
    return ExtEventStats(hours=hours, totals=t, daily=d, top_sites=s)


@router.get("/ext-analytics", response_model=ExtAnalytics)
async def read_ext_analytics(
    hours: Hours = 168,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> ExtAnalytics:
    """How the extension is used in the period: who is active, on which version,
    how far people get from finding a form to reusing an answer, what AI costs,
    which sites work, and what breaks. Counts only: no page content, no user text.
    """
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(hours=hours)
    return ExtAnalytics(
        hours=hours,
        overview=await events_repo.overview(db, since),
        versions=await events_repo.versions(db, since),
        daily=await events_repo.daily_rows(db, since),
        funnel=await events_repo.funnel(db, since),
        features=await events_repo.features(db, since),
        ai=await events_repo.ai_stats(db, since, AI_ANSWER_PURPOSE),
        sites=await events_repo.sites(db, since),
        errors=await events_repo.errors(db, since),
    )


@router.get("/users/{user_id}/ext-events", response_model=list[ExtEventRead])
async def read_user_ext_events(
    user_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ExtEventRead]:
    """One user's latest extension events, newest first: for support questions."""
    return await events_repo.timeline(db, user_id, limit)


@router.get("/ext-installs", response_model=InstallStats)
async def read_ext_installs(
    hours: Hours = 168,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> InstallStats:
    """What happened to each new install in the period, signed in or not: how far
    people got in setting up, on which browsers and systems, and the latest installs.
    """
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(hours=hours)
    return await installs_repo.stats(db, since, hours)


@router.get("/ext-installs/{install_id}/events", response_model=list[ExtEventRead])
async def read_install_journey(
    install_id: Annotated[str, Path(pattern=r"^[0-9a-f-]{36}$")],
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ExtEventRead]:
    """Everything one install did, newest first, from install to its latest use."""
    return await installs_repo.journey(db, install_id)


# ── Payments and Pro ──────────────────────────────────────────────────────────


@router.get("/billing", response_model=BillingOverview)
async def read_billing_overview(
    _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> BillingOverview:
    """Who has Pro, what came in, prices, and the latest admin changes."""
    return await billing_admin.overview(db)


@router.get("/billing/orders", response_model=Page[OrderAdminRead])
async def read_billing_orders(
    status: OrderStatus | None = None,
    kind: Literal["payment", "grant"] | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    _: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[OrderAdminRead]:
    """Every payment, given month and abandoned checkout, newest first."""
    return await billing_admin.list_orders(db, status=status, kind=kind, cursor=cursor, limit=limit)


@router.put("/billing/plans/{plan}", response_model=PlanAdminRead)
async def update_billing_plan(
    plan: Annotated[str, Path(max_length=32)],
    payload: PlanWrite,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> PlanAdminRead:
    """Changes a plan's price, length or whether it is on sale, from the next order on."""
    return await billing_admin.update_plan(db, admin_email=admin.email, plan=plan, body=payload)


@router.post("/billing/orders/{order_id}/refund", response_model=OrderAdminRead)
async def refund_billing_order(
    order_id: uuid.UUID,
    payload: NoteWrite,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> OrderAdminRead:
    """Refunds a payment in full through Razorpay and ends the Pro it bought."""
    return await billing_admin.refund(
        db, admin_email=admin.email, order_id=order_id, note=payload.note
    )


@router.post("/billing/orders/{order_id}/revoke", response_model=OrderAdminRead)
async def revoke_billing_order(
    order_id: uuid.UUID,
    payload: NoteWrite,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> OrderAdminRead:
    """Removes the Pro one payment or given month gave, without a refund."""
    return await billing_admin.revoke(
        db, admin_email=admin.email, order_id=order_id, note=payload.note
    )


@router.get("/users/{user_id}/billing", response_model=UserBillingAdmin)
async def read_user_billing(
    user_id: uuid.UUID, _: Admin = Depends(get_admin), db: AsyncSession = Depends(get_db)
) -> UserBillingAdmin:
    """One user's plan, every payment and given month, and the changes admins made."""
    return await billing_admin.user_billing(db, user_id)


@router.post("/users/{user_id}/billing/grant", response_model=OrderAdminRead, status_code=201)
async def grant_user_pro(
    user_id: uuid.UUID,
    payload: GrantWrite,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> OrderAdminRead:
    """Gives Pro for some days, after any paid time already bought."""
    return await billing_admin.grant(db, admin_email=admin.email, user_id=user_id, body=payload)


@router.post("/users/{user_id}/billing/end", response_model=UserBillingAdmin)
async def end_user_pro(
    user_id: uuid.UUID,
    payload: NoteWrite,
    admin: Admin = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
) -> UserBillingAdmin:
    """Ends someone's Pro now (every running and upcoming month), without refunds."""
    return await billing_admin.end_pro(
        db, admin_email=admin.email, user_id=user_id, note=payload.note
    )
