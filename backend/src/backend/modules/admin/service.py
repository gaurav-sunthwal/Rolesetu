"""What the admin panel can see and do."""

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import firebase_accounts, storage
from backend.core.config import get_settings
from backend.core.email import is_configured as email_is_configured
from backend.core.email import send_email
from backend.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.db.session import get_sessionmaker
from backend.modules.admin import emails, repository
from backend.modules.admin.dependencies import Admin
from backend.modules.admin.models import OutreachEmail
from backend.modules.admin.schemas import (
    AccountDeleted,
    AdminApplication,
    AdminApplicationRow,
    AdminJobCheck,
    AdminJobCheckRow,
    AdminPreviewRow,
    AdminResume,
    AdminStats,
    AdminUserDetail,
    AdminUserRow,
    AiCallRead,
    AiCallSummary,
    DailyActivity,
    DayCount,
    EmailDefaults,
    EmailTemplate,
    ErrorEventRead,
    ErrorGroup,
    ErrorSummary,
    OutreachRead,
    SiteReads,
    WaitlistRow,
)
from backend.modules.ai_calls import repository as ai_calls_repository
from backend.modules.errors import repository as errors_repository
from backend.modules.profiles import service as profiles_service

logger = logging.getLogger(__name__)

DAYS_CHARTED = 14
# "Used the extension lately" on the dashboard means in this long.
ACTIVE_FOR = timedelta(days=7)
RECENT_ROWS = 25


def _to_user_row(row: repository.Fields) -> AdminUserRow:
    (
        user,
        profiles,
        resumes,
        job_checks,
        applications,
        integrations,
        extensions,
        last_check,
        last_emailed,
    ) = row
    return AdminUserRow(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        has_profile=profiles > 0,
        resumes=resumes,
        job_checks=job_checks,
        applications=applications,
        gmail_connected=integrations > 0,
        extension_connected=extensions > 0,
        last_check_at=last_check,
        last_emailed_at=last_emailed,
    )


async def stats(db: AsyncSession) -> AdminStats:
    now = datetime.now(UTC)
    since = now - timedelta(days=DAYS_CHARTED - 1)
    found = await repository.dashboard(
        db,
        since=now - timedelta(days=1),
        active_since=now - ACTIVE_FOR,
        chart_since=since,
    )
    signups, checks, sites = (
        found.pop("signups_per_day"),
        found.pop("checks_per_day"),
        found.pop("sites"),
    )
    days = [(since + timedelta(days=offset)).date() for offset in range(DAYS_CHARTED)]
    return AdminStats(
        **found,
        daily=[
            DayCount(day=day, signups=signups.get(day, 0), job_checks=checks.get(day, 0))
            for day in days
        ],
        sites=[
            SiteReads(host=host, read=read, failed=failed, paid=paid)
            for host, read, failed, paid in sites
        ],
    )


async def list_users(
    db: AsyncSession,
    *,
    search: str | None,
    extension_missing: bool,
    has: repository.UserFilter | None = None,
    joined_on: date | None = None,
    cursor: str | None,
    limit: int,
) -> Page[AdminUserRow]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_users(
        db,
        search=search,
        extension_missing=extension_missing,
        has=has,
        active_since=datetime.now(UTC) - ACTIVE_FOR,
        joined=_day_bounds(joined_on) if joined_on else None,
        after=after,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1][0] if rows else None
    return Page(
        items=[_to_user_row(row) for row in rows],
        next_cursor=encode_cursor(last.created_at, last.id) if has_more and last else None,
    )


# The longest period the activity chart shows at once.
MAX_DAYS_CHARTED = 366


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """The start of the day and of the next, in UTC: the days the charts count by."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def daily_activity(db: AsyncSession, *, start: date, end: date) -> list[DailyActivity]:
    """One row per day from `start` to `end`, both included, oldest first."""
    if end < start:
        raise ValidationFailedError("The end date is before the start date.")
    days = (end - start).days + 1
    if days > MAX_DAYS_CHARTED:
        raise ValidationFailedError(f"Pick at most {MAX_DAYS_CHARTED} days at a time.")
    found = await repository.daily(db, since=_day_bounds(start)[0], until=_day_bounds(end)[1])
    return [
        DailyActivity(
            day=day,
            signups=found["signups"].get(day, 0),
            job_checks=found["job_checks"].get(day, 0),
            applications=found["applications"].get(day, 0),
        )
        for day in (start + timedelta(days=offset) for offset in range(days))
    ]


def _since(hours: int | None) -> datetime | None:
    return datetime.now(UTC) - timedelta(hours=hours) if hours else None


async def list_job_checks(
    db: AsyncSession,
    *,
    hours: int | None,
    day: date | None = None,
    paid: bool,
    cursor: str | None,
    limit: int,
) -> Page[AdminJobCheckRow]:
    since, until = _day_bounds(day) if day else (_since(hours), None)
    rows = await repository.all_job_checks(
        db,
        since=since,
        until=until,
        paid=paid,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[
            AdminJobCheckRow(
                id=match.id,
                created_at=match.created_at,
                user_id=match.user_id,
                user_email=email,
                role=job.role,
                company=job.company,
                url=job.url,
                status=match.status,
                score=match.score,
                error=match.error,
                paid_read=((job.job_json or {}).get("listing") or {}).get("reader") == "rendered",
            )
            for match, job, email in rows
        ],
        next_cursor=(
            encode_cursor(rows[-1][0].created_at, rows[-1][0].id) if has_more and rows else None
        ),
    )


async def list_applications(
    db: AsyncSession, *, day: date | None = None, cursor: str | None, limit: int
) -> Page[AdminApplicationRow]:
    since, until = _day_bounds(day) if day else (None, None)
    rows = await repository.all_applications(
        db,
        since=since,
        until=until,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[
            AdminApplicationRow(
                id=item.id,
                created_at=item.created_at,
                user_id=item.user_id,
                user_email=email,
                role=item.role,
                company=item.company,
                status=item.status,
                match_score=item.match_score,
                applied_at=item.applied_at,
            )
            for item, email in rows
        ],
        next_cursor=(
            encode_cursor(rows[-1][0].created_at, rows[-1][0].id) if has_more and rows else None
        ),
    )


async def list_previews(
    db: AsyncSession,
    *,
    hours: int,
    host: str | None,
    paid: bool,
    failed: bool,
    cursor: str | None,
    limit: int,
) -> Page[AdminPreviewRow]:
    rows = await repository.previews(
        db,
        since=datetime.now(UTC) - timedelta(hours=hours),
        host=host,
        paid=paid,
        failed=failed,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[
            AdminPreviewRow(
                id=row.id,
                created_at=row.created_at,
                host=row.host,
                title=(row.page or {}).get("title"),
                company=(row.page or {}).get("company"),
                read=row.page is not None,
                reader=row.reader,
            )
            for row in rows
        ],
        next_cursor=(
            encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
        ),
    )


async def user_detail(db: AsyncSession, *, user_id: uuid.UUID) -> AdminUserDetail:
    row = await repository.get_user_row(db, user_id)
    if row is None:
        raise NotFoundError("User not found")
    user = _to_user_row(row)
    profile = await profiles_service.get_profile(db, user_id=user_id) if user.has_profile else None
    checks = await repository.recent_job_checks(db, user_id, RECENT_ROWS)
    applications = await repository.recent_applications(db, user_id, RECENT_ROWS)
    return AdminUserDetail(
        user=user,
        profile=profile,
        job_checks=[
            AdminJobCheck(
                id=match.id,
                role=job.role,
                company=job.company,
                url=job.url,
                status=match.status,
                score=match.score,
                created_at=match.created_at,
            )
            for match, job in checks
        ],
        applications=[AdminApplication.model_validate(item) for item in applications],
        resumes=[
            AdminResume.model_validate(item) for item in await repository.resumes(db, user_id)
        ],
        gmail_last_synced_at=await repository.gmail_last_synced(db, user_id),
        panel_emails=[
            OutreachRead.model_validate(item)
            for item in await repository.emails_for(db, user_id, RECENT_ROWS)
        ],
    )


async def delete_user(db: AsyncSession, *, user_id: uuid.UUID, confirm_email: str) -> str:
    """Removes the account's data: the stored resume files, then the user row,
    which takes every other row with it. Returns the Firebase uid, whose
    sign-in is removed once this is committed (see `remove_sign_in`).
    """
    user = await repository.get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if confirm_email.strip().lower() != user.email.lower():
        raise ValidationFailedError("Type the account's email address exactly to confirm.")
    for resume in await repository.resumes(db, user_id):
        try:
            await storage.delete_file(resume.storage_key)
        except AppError:
            # Deleting the account must not be blocked by one unreachable file.
            logger.exception("admin delete: could not remove a resume file user=%s", user_id)
    firebase_uid = user.firebase_uid
    await db.delete(user)
    return firebase_uid


async def resume_file(
    db: AsyncSession, *, user_id: uuid.UUID, resume_id: uuid.UUID
) -> tuple[bytes, str]:
    """The resume PDF itself, for support. Returns (the file, its name)."""
    resume = await repository.resume(db, user_id, resume_id)
    if resume is None:
        raise NotFoundError("That resume was not found.")
    data = await storage.get_file(resume.storage_key)
    return data, resume.filename


async def remove_sign_in(firebase_uid: str) -> AccountDeleted:
    """Deletes the person's Firebase sign-in. Run after their data is committed
    as deleted, so a failure here can never leave data behind without a login.
    """
    try:
        await firebase_accounts.delete_sign_in(firebase_uid)
    except firebase_accounts.SignInNotRemovableError as exc:
        return AccountDeleted(
            sign_in_removed=False,
            note=f"{exc} Remove the sign-in in the Firebase console: Authentication, Users.",
        )
    return AccountDeleted(sign_in_removed=True)


async def list_waitlist(db: AsyncSession, *, cursor: str | None, limit: int) -> Page[WaitlistRow]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_waitlist(db, after=after, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[WaitlistRow.model_validate(row) for row in rows],
        next_cursor=encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None,
    )


async def ai_call_summary(db: AsyncSession, *, hours: int) -> AiCallSummary:
    since = datetime.now(UTC) - timedelta(hours=hours)
    return AiCallSummary(**await ai_calls_repository.summary(db, since))


async def list_ai_calls(
    db: AsyncSession,
    *,
    hours: int,
    source: str | None,
    user_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> Page[AiCallRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await ai_calls_repository.list_calls(
        db,
        since=datetime.now(UTC) - timedelta(hours=hours),
        source=source,
        user_id=user_id,
        after=after,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1][0] if rows else None
    return Page(
        items=[
            AiCallRead(
                id=call.id,
                created_at=call.created_at,
                user_id=call.user_id,
                user_email=email,
                source=call.source,
                purpose=call.purpose,
                model=call.model,
                own_key=call.own_key,
                ok=call.ok,
                error=call.error,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                duration_ms=call.duration_ms,
            )
            for call, email in rows
        ],
        next_cursor=encode_cursor(last.created_at, last.id) if has_more and last else None,
    )


async def list_errors(db: AsyncSession, *, hours: int, source: str | None) -> ErrorSummary:
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = await errors_repository.groups(db, since=since, source=source)
    # Two events of one problem in the same instant would otherwise list it twice.
    seen: set[str] = set()
    groups: list[ErrorGroup] = []
    for event, events, first_at, last_at in rows:
        if event.fingerprint in seen:
            continue
        seen.add(event.fingerprint)
        groups.append(
            ErrorGroup(
                fingerprint=event.fingerprint,
                source=event.source,
                level=event.level,
                route=event.route,
                method=event.method,
                status=event.status,
                code=event.code,
                message=event.message,
                events=events,
                first_at=first_at,
                last_at=last_at,
            )
        )
    return ErrorSummary(
        groups=groups,
        by_source=await errors_repository.counts_by_source(db, since),
    )


async def error_events(db: AsyncSession, *, fingerprint: str) -> list[ErrorEventRead]:
    events = await errors_repository.events_for(db, fingerprint, RECENT_ROWS * 2)
    if not events:
        raise NotFoundError("No such error. It may have been cleared.")
    return [ErrorEventRead.model_validate(event) for event in events]


async def clear_errors(db: AsyncSession, *, fingerprint: str) -> None:
    await errors_repository.delete_group(db, fingerprint)


# --- Emailing users ---------------------------------------------------------

# Most people one bulk send writes to. Gmail allows about 500 a day, shared with
# every other email the API sends.
MAX_PER_SEND = 50
# Pause between emails in a bulk send. A burst of identical emails is what a
# spammer sends; a few seconds apart reads like someone working through a list.
SECONDS_BETWEEN_SENDS = 4.0
# Someone sent this email is left alone for this long by later bulk sends.
QUIET_FOR = timedelta(days=14)
# One person is not written to twice within this time, to stop a double click.
ONE_EMAIL_PER = timedelta(hours=24)


def _require_email_set_up() -> None:
    if not email_is_configured():
        raise ValidationFailedError(
            "Email is not set up on the server. Add GMAIL_SENDER_REFRESH_TOKEN to send "
            "from the panel."
        )


async def email_defaults(db: AsyncSession) -> EmailDefaults:
    recipients = await repository.count_nudge_recipients(db, datetime.now(UTC) - QUIET_FOR)
    return EmailDefaults(
        subject=emails.DEFAULT_SUBJECT,
        message=emails.DEFAULT_MESSAGE,
        placeholder=emails.PLACEHOLDER,
        recipients=recipients,
        max_per_send=MAX_PER_SEND,
        configured=email_is_configured(),
    )


async def _deliver(
    db: AsyncSession,
    *,
    admin_email: str,
    user_id: uuid.UUID,
    address: str,
    name: str | None,
    subject: str,
    message: str,
    kind: str = emails.NUDGE,
) -> OutreachEmail:
    """Sends one email and records how it went. Never raises for a failed send."""
    if kind == emails.FOUNDER_NOTE:
        email = emails.founder_note(subject=subject, message=message, name=emails.first_name(name))
    else:
        email = emails.extension_nudge(
            subject=subject,
            message=message,
            name=emails.first_name(name),
            store_url=get_settings().extension_store_url,
        )
    record = OutreachEmail(
        id=uuid.uuid4(),
        user_id=user_id,
        admin_email=admin_email,
        kind=kind,
        subject=email.subject[:200],
        status="sent",
    )
    try:
        await send_email(
            to=address,
            subject=email.subject,
            html=None,
            text=email.text,
            # Names this one email, so a retry never delivers a second copy.
            idempotency_key=f"outreach-{record.id}",
            sender_name=emails.SENDER_NAME,
        )
    except Exception as exc:
        logger.warning("admin email to user=%s failed: %s", user_id, type(exc).__name__)
        record.status = "failed"
        record.error = "The email service refused or did not answer. Try again later."
    db.add(record)
    return record


async def email_templates(db: AsyncSession, user_id: uuid.UUID) -> list[EmailTemplate]:
    """Ready-made notes for this person, filled in with what they have done."""
    row = await repository.get_user_row(db, user_id)
    if row is None:
        raise NotFoundError("User not found")
    user, _, _, job_checks, applications, _, extensions, _, _ = row
    usage = emails.Usage(
        joined_at=user.created_at,
        job_checks=job_checks,
        applications=applications,
        has_extension=extensions > 0,
    )
    return [
        EmailTemplate.model_validate(template.__dict__)
        for template in emails.templates_for(usage, datetime.now(UTC))
    ]


async def email_user(
    db: AsyncSession,
    *,
    admin: Admin,
    user_id: uuid.UUID,
    subject: str,
    message: str,
    kind: str = emails.NUDGE,
) -> OutreachRead:
    _require_email_set_up()
    user = await repository.get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if await repository.sent_lately(db, user_id, datetime.now(UTC) - ONE_EMAIL_PER):
        raise ConflictError(
            "This person was emailed in the last 24 hours. Wait before writing again."
        )
    name = await repository.full_name(db, user_id) or user.name
    record = await _deliver(
        db,
        admin_email=admin.email,
        user_id=user_id,
        address=user.email,
        name=name,
        subject=subject,
        message=message,
        kind=kind,
    )
    await db.flush()
    return OutreachRead.model_validate(record)


async def start_extension_nudges(db: AsyncSession, *, subject: str, message: str) -> int:
    """How many people the send will reach. The sending itself runs after the
    response (see send_extension_nudges), since it takes a while.
    """
    _require_email_set_up()
    count = await repository.count_nudge_recipients(db, datetime.now(UTC) - QUIET_FOR)
    return min(count, MAX_PER_SEND)


async def send_extension_nudges(admin_email: str, subject: str, message: str) -> None:
    """Writes to everyone without the extension who was not written to lately,
    one at a time, recording each. Runs in the background in its own session.
    """
    async with get_sessionmaker()() as db:
        recipients = await repository.nudge_recipients(
            db, datetime.now(UTC) - QUIET_FOR, MAX_PER_SEND
        )
        for user, full_name in recipients:
            await _deliver(
                db,
                admin_email=admin_email,
                user_id=user.id,
                address=user.email,
                name=full_name or user.name,
                subject=subject,
                message=message,
            )
            # Committed one by one, so a crash part way keeps the record of who was written to.
            await db.commit()
            await asyncio.sleep(SECONDS_BETWEEN_SENDS)
