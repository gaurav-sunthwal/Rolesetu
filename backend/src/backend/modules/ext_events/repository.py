"""Database helpers for extension usage events."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.ext_events.models import ExtEvent
from backend.modules.ext_events.schemas import (
    ExtEventDay,
    ExtEventSiteRow,
    ExtEventTotals,
)

KEEP_FOR = timedelta(days=90)


async def insert_events(
    db: AsyncSession,
    user_id,
    events: list[dict],
) -> None:
    """Bulk-insert a batch of events for one user."""
    for ev in events:
        db.add(ExtEvent(user_id=user_id, **ev))
    # Prune old rows in the same transaction (cheap: index-only scan).
    cutoff = datetime.now(UTC) - KEEP_FOR
    await db.execute(delete(ExtEvent).where(ExtEvent.created_at < cutoff))


async def totals(db: AsyncSession, since: datetime) -> ExtEventTotals:
    """Aggregate counts for all event names since a given UTC datetime."""
    rows = await db.execute(
        select(ExtEvent.name, func.count().label("n"))
        .where(ExtEvent.created_at >= since)
        .group_by(ExtEvent.name)
    )
    counts: dict[str, int] = {row.name: row.n for row in rows}
    offered = counts.get("autofill_offered", 0)
    filled = counts.get("autofill_filled", 0)
    fill_rate = round(filled * 100 / offered) if offered else 0
    return ExtEventTotals(
        autofill_offered=offered,
        autofill_filled=filled,
        autofill_failed=counts.get("autofill_failed", 0),
        autofill_learned=counts.get("autofill_learned", 0),
        job_scored=counts.get("job_scored", 0),
        panel_opened=counts.get("panel_opened", 0),
        apply_clicked=counts.get("apply_clicked", 0),
        fill_rate_pct=fill_rate,
    )


async def daily(db: AsyncSession, since: datetime) -> list[ExtEventDay]:
    """Per-day breakdown for the last N days chart."""
    rows = await db.execute(
        select(
            func.date_trunc("day", ExtEvent.created_at).label("day"),
            ExtEvent.name,
            func.count().label("n"),
        )
        .where(
            ExtEvent.created_at >= since,
            ExtEvent.name.in_(
                ["autofill_offered", "autofill_filled", "job_scored", "apply_clicked"]
            ),
        )
        .group_by(text("1"), ExtEvent.name)
        .order_by(text("1"))
    )
    # Pivot: collect per-day, per-name counts into ExtEventDay objects.
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        day_str = row.day.strftime("%Y-%m-%d")
        if day_str not in buckets:
            buckets[day_str] = {}
        buckets[day_str][row.name] = row.n

    return [
        ExtEventDay(
            day=day,
            autofill_offered=counts.get("autofill_offered", 0),
            autofill_filled=counts.get("autofill_filled", 0),
            job_scored=counts.get("job_scored", 0),
            apply_clicked=counts.get("apply_clicked", 0),
        )
        for day, counts in sorted(buckets.items())
    ]


async def top_sites(db: AsyncSession, since: datetime, limit: int = 20) -> list[ExtEventSiteRow]:
    """Top sites ordered by autofill_offered, with fill rates."""
    rows = await db.execute(
        select(
            ExtEvent.host,
            ExtEvent.name,
            func.count().label("n"),
        )
        .where(
            ExtEvent.created_at >= since,
            ExtEvent.host.isnot(None),
            ExtEvent.name.in_(["autofill_offered", "autofill_filled"]),
        )
        .group_by(ExtEvent.host, ExtEvent.name)
        .order_by(func.count().desc())
    )
    # Aggregate into host → {offered, filled}.
    data: dict[str, dict[str, int]] = {}
    for row in rows:
        if row.host not in data:
            data[row.host] = {}
        data[row.host][row.name] = row.n

    result = [
        ExtEventSiteRow(
            host=host,
            offered=counts.get("autofill_offered", 0),
            filled=counts.get("autofill_filled", 0),
            fill_rate_pct=round(counts.get("autofill_filled", 0) * 100 / counts["autofill_offered"])
            if counts.get("autofill_offered")
            else 0,
        )
        for host, counts in data.items()
    ]
    # Sort by offered desc, take top N.
    result.sort(key=lambda r: r.offered, reverse=True)
    return result[:limit]
