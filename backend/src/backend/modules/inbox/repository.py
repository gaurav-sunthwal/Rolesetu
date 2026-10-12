import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.applications.models import Application
from backend.modules.inbox.models import EmailMessage, Integration, Interview
from backend.modules.matches.models import Match

PROVIDER = "gmail"


async def get_integration(db: AsyncSession, user_id: uuid.UUID) -> Integration | None:
    result = await db.execute(
        select(Integration).where(Integration.user_id == user_id, Integration.provider == PROVIDER)
    )
    return result.scalar_one_or_none()


async def known_gmail_ids(db: AsyncSession, user_id: uuid.UUID, ids: Sequence[str]) -> set[str]:
    if not ids:
        return set()
    result = await db.execute(
        select(EmailMessage.gmail_message_id).where(
            EmailMessage.user_id == user_id, EmailMessage.gmail_message_id.in_(ids)
        )
    )
    return set(result.scalars())


async def get_message(
    db: AsyncSession, user_id: uuid.UUID, message_id: uuid.UUID
) -> EmailMessage | None:
    result = await db.execute(
        select(EmailMessage).where(EmailMessage.id == message_id, EmailMessage.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    state: str | None,
    application_id: uuid.UUID | None = None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[EmailMessage]:
    query = select(EmailMessage).where(EmailMessage.user_id == user_id)
    if state:
        query = query.where(EmailMessage.state == state)
    if application_id:
        query = query.where(EmailMessage.application_id == application_id)
    if after:
        received_at, row_id = after
        query = query.where(
            or_(
                EmailMessage.received_at < received_at,
                and_(EmailMessage.received_at == received_at, EmailMessage.id < row_id),
            )
        )
    query = query.order_by(EmailMessage.received_at.desc(), EmailMessage.id.desc()).limit(limit)
    return list((await db.execute(query)).scalars())


async def count_in_review(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(EmailMessage)
        .where(EmailMessage.user_id == user_id, EmailMessage.state == "review")
    )
    return result.scalar_one()


async def delete_messages(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(EmailMessage).where(EmailMessage.user_id == user_id))


async def applications_of(db: AsyncSession, user_id: uuid.UUID) -> list[Application]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
        .limit(2000)
    )
    return list(result.scalars())


async def get_application(
    db: AsyncSession, user_id: uuid.UUID, application_id: uuid.UUID
) -> Application | None:
    result = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def latest_match_per_job(
    db: AsyncSession, user_id: uuid.UUID, job_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Match]:
    """The most recent completed job check for each job, for this user."""
    if not job_ids:
        return {}
    result = await db.execute(
        select(Match)
        .where(Match.user_id == user_id, Match.job_id.in_(job_ids), Match.status == "completed")
        .order_by(Match.created_at.desc())
    )
    latest: dict[uuid.UUID, Match] = {}
    for match in result.scalars():
        latest.setdefault(match.job_id, match)
    return latest


async def trim_messages(db: AsyncSession, user_id: uuid.UUID, keep: int) -> None:
    """Deletes all but the newest `keep` mail records."""
    newest = (
        select(EmailMessage.id)
        .where(EmailMessage.user_id == user_id)
        .order_by(EmailMessage.received_at.desc(), EmailMessage.id.desc())
        .limit(keep)
    )
    await db.execute(
        delete(EmailMessage).where(EmailMessage.user_id == user_id, EmailMessage.id.not_in(newest))
    )


async def list_interviews(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Interview, str | None, str | None]]:
    """Each interview with the subject and Gmail id of the mail it came from. Soonest first;
    ones with no time yet come first of all, because they need attention.
    """
    result = await db.execute(
        select(Interview, EmailMessage.subject, EmailMessage.gmail_message_id)
        .outerjoin(EmailMessage, EmailMessage.id == Interview.email_message_id)
        .where(Interview.user_id == user_id)
        .order_by(Interview.starts_at.asc().nulls_first(), Interview.created_at.desc())
        .limit(200)
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def get_interview(
    db: AsyncSession, user_id: uuid.UUID, interview_id: uuid.UUID
) -> Interview | None:
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def open_interview_for(
    db: AsyncSession, user_id: uuid.UUID, application_id: uuid.UUID, after: datetime
) -> Interview | None:
    """The interview for this application that has not happened yet (or has no
    time yet): the one a reminder or a reschedule mail is about.
    """
    result = await db.execute(
        select(Interview)
        .where(
            Interview.user_id == user_id,
            Interview.application_id == application_id,
            or_(Interview.starts_at.is_(None), Interview.starts_at >= after),
        )
        .order_by(Interview.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def latest_mail_per_application(
    db: AsyncSession, user_id: uuid.UUID, application_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """For each application, the Gmail id of the newest mail about it."""
    if not application_ids:
        return {}
    result = await db.execute(
        select(EmailMessage.application_id, EmailMessage.gmail_message_id)
        .where(
            EmailMessage.user_id == user_id,
            EmailMessage.application_id.in_(application_ids),
        )
        .order_by(EmailMessage.received_at.desc())
    )
    latest: dict[uuid.UUID, str] = {}
    for application_id, gmail_id in result.all():
        if application_id is not None:
            latest.setdefault(application_id, gmail_id)
    return latest
