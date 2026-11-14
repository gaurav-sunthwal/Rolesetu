"""A user's job hunt as a year of days, like a contribution graph: how many jobs they
applied to, checked, worked on in the extension or got AI help with, each day, and
their streaks.

Counted from what each feature already records, scoped to the one user, and grouped
by day in the user's own time zone so "today" means their today.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.answer_writer import PURPOSE as AI_ANSWER_PURPOSE
from backend.modules.activity.schemas import ActivityDay, ActivityYear, Streaks

# 53 weeks, so the grid fills whole columns like GitHub's.
DAYS_SHOWN = 371

_PER_DAY = text(
    """
    WITH acts AS (
        SELECT 'applications' AS kind, created_at FROM applications
         WHERE user_id = :user_id AND created_at >= :since
        UNION ALL
        SELECT 'job_checks', created_at FROM matches
         WHERE user_id = :user_id AND created_at >= :since
        UNION ALL
        SELECT 'extension', created_at FROM ext_events
         WHERE user_id = :user_id AND created_at >= :since
           AND name IN ('job_scored', 'autofill_filled', 'suggestion_used', 'answer_saved')
        UNION ALL
        SELECT 'ai', created_at FROM ai_calls
         WHERE user_id = :user_id AND created_at >= :since AND ok
           AND purpose IN (:ai_answer, 'resume-assistant')
    )
    SELECT (created_at AT TIME ZONE :tz)::date AS day, kind, count(*) AS n
    FROM acts
    GROUP BY 1, 2
    """
)


def _zone(name: str | None) -> str:
    """A real IANA time zone name, or UTC. Never passes anything else to the database."""
    if name:
        try:
            ZoneInfo(name)
            return name
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return "UTC"


def streaks(active: list[bool]) -> Streaks:
    """`active` is one flag per day, oldest first, ending today. The current streak
    may end yesterday: a day without activity yet does not break it until it is over."""
    longest = run = 0
    for flag in active:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    current = 0
    days = active[:-1] if active and not active[-1] else active
    for flag in reversed(days):
        if not flag:
            break
        current += 1
    return Streaks(current=current, longest=longest, active_days=sum(active))


async def year(db: AsyncSession, *, user_id: uuid.UUID, timezone: str | None) -> ActivityYear:
    tz = _zone(timezone)
    today = datetime.now(ZoneInfo(tz)).date()
    start = today - timedelta(days=DAYS_SHOWN - 1)
    # A day early in UTC, so the first local day is counted in full; extra rows are
    # dropped below.
    since = datetime.combine(start, datetime.min.time(), UTC) - timedelta(days=1)
    rows = (
        await db.execute(
            _PER_DAY,
            {"user_id": user_id, "since": since, "tz": tz, "ai_answer": AI_ANSWER_PURPOSE},
        )
    ).all()

    by_day: dict[date, ActivityDay] = {}
    for day, kind, count in rows:
        if start <= day <= today:
            entry = by_day.setdefault(day, ActivityDay(date=day))
            setattr(entry, kind, getattr(entry, kind) + int(count))

    days = [
        by_day.get(start + timedelta(days=i)) or ActivityDay(date=start + timedelta(days=i))
        for i in range(DAYS_SHOWN)
    ]
    totals = ActivityDay(
        date=today,
        applications=sum(d.applications for d in days),
        job_checks=sum(d.job_checks for d in days),
        extension=sum(d.extension for d in days),
        ai=sum(d.ai for d in days),
    )
    return ActivityYear(
        start=start,
        end=today,
        timezone=tz,
        days=days,
        totals=totals,
        # The streak is days in a row with at least one job applied to.
        streaks=streaks([d.applications > 0 for d in days]),
    )
