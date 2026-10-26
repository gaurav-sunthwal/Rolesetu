import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.applications.models import Application
from backend.modules.career_jobs.audience import Audience, audience_from
from backend.modules.profiles.models import Profile


async def load_audience(db: AsyncSession) -> Audience:
    """Counts users per experience band. Reads only the experience column."""
    rows = (await db.execute(select(Profile.experience))).scalars().all()
    return audience_from([list(row or []) for row in rows], date.today())


async def tracked_urls(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """Links of every job this user already tracks, however it was added."""
    rows = await db.execute(
        select(Application.url).where(Application.user_id == user_id, Application.url.is_not(None))
    )
    return {same_job(url) for url in rows.scalars() if url}


def same_job(url: str) -> str:
    """One form of a job link, so a trailing slash or letter case does not hide a match."""
    return url.strip().rstrip("/").lower()
