import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from cryptography.fernet import InvalidToken
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.encryption import decrypt_text, encrypt_text
from backend.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.db.session import get_sessionmaker
from backend.modules.applications.models import Application, ApplicationEvent
from backend.modules.inbox import gmail, repository
from backend.modules.inbox.classifier import Classified, classify
from backend.modules.inbox.insights import Outcome, find_patterns
from backend.modules.inbox.linking import STATUS_FOR_KIND, find_application, next_status
from backend.modules.inbox.models import EmailMessage, Integration, Interview
from backend.modules.inbox.schedule import find_schedule
from backend.modules.inbox.schemas import (
    EmailRead,
    FindingRead,
    InboxInsights,
    InboxStatus,
    InterviewRead,
    InterviewUpdate,
    ReviewAction,
    Totals,
)

logger = logging.getLogger(__name__)

# The consent screen must be finished within this long of pressing Connect.
STATE_VALID_SECONDS = 600
MAX_MAILS_PER_SYNC = 200
# Gmail limits how fast one mailbox may be read, so mails are fetched a few at
# a time, and saved in batches so a sync that is cut short keeps its progress.
READ_AT_ONCE = 2
BATCH = 20
# Mail records kept per person: the newest ones. Each is a few hundred bytes
# (no body), so this is generous without letting a mailbox grow without end.
KEEP_MAIL_RECORDS = 500
# A sync that has shown "syncing" for longer than this crashed; let another start.
SYNC_GIVES_UP_AFTER = timedelta(minutes=10)

# Only mail that can be about an application is asked for, so unrelated mail
# never leaves Google. The classifier then decides what each one is.
_SEARCH = (
    "-from:me (subject:(application OR applied OR applying OR candidature OR interview OR "
    "assessment OR shortlisted OR offer OR unfortunately) OR "
    '"thank you for applying" OR "your application" OR "regret to inform" OR '
    '"application was sent" OR "application received" OR '
    "from:(greenhouse.io OR lever.co OR ashbyhq.com OR myworkday.com OR workable.com OR "
    "smartrecruiters.com OR icims.com OR internshala.com OR naukri.com))"
)
ROLE_NOT_STATED = "Role not stated"


class InvalidConnectStateError(Exception):
    pass


@dataclass
class SyncResult:
    read: int = 0
    kept: int = 0
    linked: int = 0
    created: int = 0
    review: int = 0


# --- connecting


def connect_url(user_id: uuid.UUID) -> str:
    """Google's consent page. `state` carries who asked, encrypted, so the
    callback (which the browser reaches without our login header) knows whose
    mailbox this is and cannot be pointed at another account.
    """
    state = encrypt_text(f"{user_id}|{int(time.time())}")
    return gmail.consent_url(state)


def _user_from_state(state: str) -> uuid.UUID:
    try:
        user_id, issued = decrypt_text(state).split("|", 1)
        if time.time() - int(issued) > STATE_VALID_SECONDS:
            raise InvalidConnectStateError
        return uuid.UUID(user_id)
    except (InvalidToken, ValueError) as exc:
        raise InvalidConnectStateError from exc


async def finish_connecting(db: AsyncSession, *, code: str, state: str) -> uuid.UUID:
    user_id = _user_from_state(state)
    refresh_token, access_token = await gmail.exchange_code(code)
    address = await gmail.GmailMailbox(access_token).address()

    integration = await repository.get_integration(db, user_id)
    if integration is None:
        integration = Integration(user_id=user_id, provider=repository.PROVIDER, scopes=gmail.SCOPE)
        db.add(integration)
    integration.account_email = address
    integration.encrypted_refresh_token = encrypt_text(refresh_token)
    integration.scopes = gmail.SCOPE
    integration.last_error = None
    await db.flush()
    return user_id


async def disconnect(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Removes the connection and every mail record. Applications stay: they
    are the user's own tracker, not mailbox data.
    """
    integration = await repository.get_integration(db, user_id)
    if integration is None:
        return
    await gmail.revoke(decrypt_text(integration.encrypted_refresh_token))
    await repository.delete_messages(db, user_id)
    await db.delete(integration)


def _is_syncing(integration: Integration, now: datetime) -> bool:
    started = integration.sync_started_at
    return (
        integration.sync_status == "syncing"
        and started is not None
        and now - started < SYNC_GIVES_UP_AFTER
    )


async def get_status(db: AsyncSession, *, user_id: uuid.UUID) -> InboxStatus:
    settings = get_settings()
    integration = await repository.get_integration(db, user_id)
    now = datetime.now(UTC)
    return InboxStatus(
        configured=bool(settings.google_client_id and settings.google_client_secret),
        connected=integration is not None,
        account_email=integration.account_email if integration else None,
        sync_status="syncing" if integration and _is_syncing(integration, now) else "idle",
        last_synced_at=integration.last_synced_at if integration else None,
        last_error=integration.last_error if integration else None,
        lookback_days=settings.inbox_lookback_days,
        review_count=await repository.count_in_review(db, user_id),
    )


# --- syncing


def _apply(application: Application, kind: str, when: datetime) -> bool:
    """Moves the application's status for this mail. Returns whether it moved."""
    status = next_status(application.status, kind)
    if status is None:
        return False
    application.status = status
    if application.applied_at is None:
        application.applied_at = when
    return True


async def _note_interview(
    db: AsyncSession,
    user_id: uuid.UUID,
    mail: gmail.RawMail,
    record: EmailMessage,
    found: Classified,
    application: Application | None,
) -> None:
    """Records the interview a mail announces, or updates the one already
    recorded when this mail is a reminder or a reschedule.
    """
    schedule = find_schedule(
        f"{mail.subject}\n{mail.body}",
        sent_at=mail.received_at,
        sender_offset_minutes=mail.sender_offset_minutes,
        calendar=mail.calendar,
    )
    existing = (
        await repository.open_interview_for(db, user_id, application.id, mail.received_at)
        if application is not None
        else None
    )
    if existing is None:
        await db.flush()  # the mail record needs its id before it is pointed at
        db.add(
            Interview(
                user_id=user_id,
                application_id=application.id if application else None,
                email_message_id=record.id,
                company=application.company if application else found.company,
                role=(application.role if application else None) or found.role,
                starts_at=schedule.starts_at,
                ends_at=schedule.ends_at,
                has_time=schedule.has_time,
                link=schedule.link,
                location=schedule.location,
            )
        )
        return
    if existing.edited:
        return  # the user set this one themselves
    # A later mail with a time replaces an earlier one without, or an earlier time.
    if schedule.starts_at is not None and (schedule.has_time or not existing.has_time):
        existing.starts_at, existing.ends_at = schedule.starts_at, schedule.ends_at
        existing.has_time = schedule.has_time
        existing.email_message_id = record.id
    existing.link = schedule.link or existing.link
    existing.location = schedule.location or existing.location


async def _place(
    db: AsyncSession,
    user_id: uuid.UUID,
    mail: gmail.RawMail,
    found: Classified,
    applications: list[Application],
    result: SyncResult,
) -> None:
    """Stores the mail and updates the tracker for it."""
    record = EmailMessage(
        user_id=user_id,
        gmail_message_id=mail.id,
        sender_name=mail.sender_name,
        sender_email=mail.sender_email,
        subject=mail.subject,
        received_at=mail.received_at,
        kind=found.kind,
        company=found.company,
        role=found.role,
        state="review",
    )
    try:
        # Its own savepoint: if another sync recorded this mail a moment ago, only
        # this insert is undone and the rest of the batch carries on.
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        return
    result.kept += 1

    target = find_application(
        applications,
        found.company,
        found.role,
        new_application=found.kind == "applied",
        unnamed_role=ROLE_NOT_STATED,
    )
    if found.kind == "unclear" or target == "ambiguous":
        result.review += 1
        if found.kind == "interview":
            await _note_interview(db, user_id, mail, record, found, None)
        return

    if target == "none":
        # The user applied somewhere we were not tracking: start tracking it.
        assert found.company is not None  # "none" is only returned for a named company
        application = Application(
            user_id=user_id,
            role=found.role or ROLE_NOT_STATED,
            company=found.company,
            status=STATUS_FOR_KIND[found.kind],
            applied_at=mail.received_at,
        )
        application.events = [
            ApplicationEvent(type=application.status, source="gmail", occurred_at=mail.received_at)
        ]
        db.add(application)
        await db.flush()
        applications.append(application)
        record.state, record.application_id = "created", application.id
        result.created += 1
        if found.kind == "interview":
            await _note_interview(db, user_id, mail, record, found, application)
        return

    if _apply(target, found.kind, mail.received_at):
        db.add(
            ApplicationEvent(
                application_id=target.id,
                type=target.status,
                source="gmail",
                occurred_at=mail.received_at,
            )
        )
    if target.role == ROLE_NOT_STATED and found.role:
        target.role = found.role  # a later mail named the role an earlier one left out
    record.state, record.application_id = "linked", target.id
    result.linked += 1
    if found.kind == "interview":
        await _note_interview(db, user_id, mail, record, found, target)


async def sync_mailbox(
    db: AsyncSession, user_id: uuid.UUID, mailbox: gmail.Mailbox, *, days: int
) -> SyncResult:
    """Reads recent job mail and brings the tracker up to date. Safe to run
    again: a mail already recorded is skipped.
    """
    result = SyncResult()
    ids = await mailbox.list_ids(f"newer_than:{days}d {_SEARCH}", MAX_MAILS_PER_SYNC)
    known = await repository.known_gmail_ids(db, user_id, ids)
    new_ids = [message_id for message_id in ids if message_id not in known]

    gate = asyncio.Semaphore(READ_AT_ONCE)

    async def read(message_id: str) -> gmail.RawMail:
        async with gate:
            return await mailbox.read(message_id)

    applications = await repository.applications_of(db, user_id)
    # Gmail lists newest first. Reading from the oldest end means an application
    # moves through its statuses in the order things actually happened.
    oldest_first = list(reversed(new_ids))
    for start in range(0, len(oldest_first), BATCH):
        mails = await asyncio.gather(*(read(mid) for mid in oldest_first[start : start + BATCH]))
        result.read += len(mails)
        for mail in sorted(mails, key=lambda item: item.received_at):
            found = classify(mail.subject, mail.sender_name, mail.sender_email, mail.body)
            if found is not None:
                await _place(db, user_id, mail, found, applications, result)
        # Saved now: if a later batch fails, the next sync carries on from here.
        await db.commit()
    await repository.trim_messages(db, user_id, KEEP_MAIL_RECORDS)
    await db.commit()
    return result


async def start_sync(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Marks a sync as started. The reading itself runs after the response."""
    integration = await repository.get_integration(db, user_id)
    if integration is None:
        raise NotFoundError("Connect Gmail first.")
    now = datetime.now(UTC)
    if _is_syncing(integration, now):
        raise ConflictError("Your inbox is already being read. This takes under a minute.")
    integration.sync_status = "syncing"
    integration.sync_started_at = now


async def run_sync(user_id: uuid.UUID) -> None:
    """Runs after the response has been sent, in its own database session."""
    settings = get_settings()
    async with get_sessionmaker()() as db:
        integration = await repository.get_integration(db, user_id)
        if integration is None:
            return
        now = datetime.now(UTC)
        # Later syncs only need to cover the time since the last one, plus a day of overlap.
        days = settings.inbox_lookback_days
        if integration.last_synced_at is not None:
            days = min(days, (now - integration.last_synced_at).days + 2)
        error: str | None = None
        try:
            token = await gmail.access_token_for(decrypt_text(integration.encrypted_refresh_token))
            await sync_mailbox(db, user_id, gmail.GmailMailbox(token), days=days)
        except gmail.GmailAccessLostError:
            await db.rollback()
            error = "Gmail access has expired or was removed. Connect Gmail again."
        except gmail.GmailBusyError:
            await db.rollback()
            error = (
                "Gmail asked us to slow down. What was read so far is saved: "
                "press Sync now in a minute to read the rest."
            )
        except gmail.GmailApiOffError:
            await db.rollback()
            error = "The Gmail API is switched off for this app's Google Cloud project."
        except Exception:
            logger.exception("Inbox sync failed for user %s", user_id)
            await db.rollback()
            error = "Your inbox could not be read just now. Please try again."

        integration = await repository.get_integration(db, user_id)
        if integration is not None:
            integration.sync_status = "idle"
            integration.last_error = error
            if error is None:
                integration.last_synced_at = now
        await db.commit()


# --- reading


def gmail_link(account_email: str | None, gmail_message_id: str | None) -> str | None:
    """A link that opens one mail in Gmail's own site. `authuser` picks the
    right account when the browser is signed in to several.
    """
    if not account_email or not gmail_message_id:
        return None
    return f"https://mail.google.com/mail/?authuser={quote(account_email)}#all/{gmail_message_id}"


async def _account_email(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    integration = await repository.get_integration(db, user_id)
    return integration.account_email if integration else None


def _email(row: EmailMessage, account_email: str | None) -> EmailRead:
    read = EmailRead.model_validate(row)
    read.gmail_url = gmail_link(account_email, row.gmail_message_id)
    return read


async def list_messages(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    state: str | None,
    application_id: uuid.UUID | None = None,
    cursor: str | None,
    limit: int,
) -> Page[EmailRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_messages(
        db, user_id, state=state, application_id=application_id, after=after, limit=limit + 1
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].received_at, rows[-1].id) if has_more and rows else None
    account = await _account_email(db, user_id)
    return Page(items=[_email(row, account) for row in rows], next_cursor=next_cursor)


async def resolve(
    db: AsyncSession, *, user_id: uuid.UUID, message_id: uuid.UUID, payload: ReviewAction
) -> EmailRead:
    """The user settles a mail we were unsure about."""
    message = await repository.get_message(db, user_id, message_id)
    if message is None:
        raise NotFoundError("That mail is no longer in your list.")
    if payload.action == "dismiss":
        message.state, message.application_id = "dismissed", None
        await db.flush()
        return _email(message, await _account_email(db, user_id))

    assert payload.application_id is not None  # checked by the schema
    application = await repository.get_application(db, user_id, payload.application_id)
    if application is None:
        raise ValidationFailedError("That application does not exist.")
    if _apply(application, message.kind, message.received_at):
        db.add(
            ApplicationEvent(
                application_id=application.id,
                type=application.status,
                source="gmail",
                occurred_at=message.received_at,
            )
        )
    message.state, message.application_id = "linked", application.id
    await db.flush()
    return _email(message, await _account_email(db, user_id))


async def get_insights(db: AsyncSession, *, user_id: uuid.UUID) -> InboxInsights:
    applications = await repository.applications_of(db, user_id)
    matches = await repository.latest_match_per_job(
        db, user_id, [item.job_id for item in applications if item.job_id]
    )
    outcomes: list[Outcome] = []
    for application in applications:
        match = matches.get(application.job_id) if application.job_id else None
        experience = (match.experience or {}) if match else {}
        outcomes.append(
            Outcome(
                status=application.status,
                score=match.score if match else application.match_score,
                experience_status=experience.get("status"),
                required_years=experience.get("required_min"),
                gaps=tuple(match.gaps) if match else (),
                checked=match is not None,
            )
        )

    def count(*statuses: str) -> int:
        return sum(1 for item in outcomes if item.status in statuses)

    return InboxInsights(
        totals=Totals(
            applied=count("applied", "replied", "interview", "offer", "rejected"),
            waiting=count("applied"),
            rejected=count("rejected"),
            interviews=count("interview"),
            offers=count("offer"),
        ),
        findings=[
            FindingRead(title=item.title, detail=item.detail) for item in find_patterns(outcomes)
        ],
    )


# --- interviews


def _interview(
    row: Interview, subject: str | None = None, gmail_url: str | None = None
) -> InterviewRead:
    read = InterviewRead.model_validate(row)
    read.mail_subject, read.gmail_url = subject, gmail_url
    return read


async def list_interviews(db: AsyncSession, *, user_id: uuid.UUID) -> list[InterviewRead]:
    rows = await repository.list_interviews(db, user_id)
    account = await _account_email(db, user_id)
    return [
        _interview(row, subject, gmail_link(account, gmail_id)) for row, subject, gmail_id in rows
    ]


async def update_interview(
    db: AsyncSession, *, user_id: uuid.UUID, interview_id: uuid.UUID, payload: InterviewUpdate
) -> InterviewRead:
    interview = await repository.get_interview(db, user_id, interview_id)
    if interview is None:
        raise NotFoundError("That interview is no longer in your list.")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        # An emptied text box means "remove this", not "store an empty string".
        setattr(interview, field, None if value == "" else value)
    if "starts_at" in changes:
        interview.has_time = changes["starts_at"] is not None
        if changes["starts_at"] is None or (
            interview.ends_at is not None and interview.ends_at <= changes["starts_at"]
        ):
            interview.ends_at = None
    interview.edited = True
    await db.flush()
    return _interview(interview)


async def delete_interview(
    db: AsyncSession, *, user_id: uuid.UUID, interview_id: uuid.UUID
) -> None:
    interview = await repository.get_interview(db, user_id, interview_id)
    if interview is None:
        raise NotFoundError("That interview is no longer in your list.")
    await db.delete(interview)
