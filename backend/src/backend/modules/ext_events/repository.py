"""Database helpers for extension usage events."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, distinct, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.ai_calls.models import AiCall
from backend.modules.ext_events.models import ExtEvent
from backend.modules.ext_events.schemas import (
    ExtAiStats,
    ExtCountRow,
    ExtDayRow,
    ExtErrorRow,
    ExtEventDay,
    ExtEventRead,
    ExtEventSiteRow,
    ExtEventTotals,
    ExtFeatureRow,
    ExtFunnelStep,
    ExtOverview,
    ExtSiteRow,
    ExtVersionRow,
)

KEEP_FOR = timedelta(days=90)

# The path from finding a form to reusing an answer, in order.
FUNNEL = [
    ("form_detected", "Found an application form"),
    ("autofill_offered", "Offered to fill it"),
    ("autofill_filled", "Filled it"),
    ("answer_saved", "Saved an answer"),
    ("suggestion_used", "Reused an answer"),
]


async def insert_events(db: AsyncSession, user_id: uuid.UUID, events: list[dict[str, Any]]) -> None:
    """Stores a batch for one user. An event already stored (same id: a retried
    batch) is skipped, so counts are never inflated by retries."""
    if events:
        statement = insert(ExtEvent).values(
            [{"id": uuid.uuid4(), "user_id": user_id, **event} for event in events]
        )
        await db.execute(
            statement.on_conflict_do_nothing(
                index_elements=["client_id"], index_where=text("client_id IS NOT NULL")
            )
        )
    # Prune old rows in the same transaction (cheap: index scan).
    cutoff = datetime.now(UTC) - KEEP_FOR
    await db.execute(delete(ExtEvent).where(ExtEvent.created_at < cutoff))


def _named(name: str) -> Any:
    return func.count().filter(ExtEvent.name == name)


def _users_with(name: str) -> Any:
    return func.count(distinct(ExtEvent.user_id)).filter(ExtEvent.name == name)


async def overview(db: AsyncSession, since: datetime) -> ExtOverview:
    now = datetime.now(UTC)
    active = await db.execute(
        select(
            func.count(distinct(ExtEvent.user_id)).filter(
                ExtEvent.created_at >= now - timedelta(days=1)
            ),
            func.count(distinct(ExtEvent.user_id)).filter(
                ExtEvent.created_at >= now - timedelta(days=7)
            ),
            func.count(distinct(ExtEvent.user_id)),
        ).where(ExtEvent.created_at >= now - timedelta(days=30))
    )
    active_1d, active_7d, active_30d = active.one()
    period = await db.execute(
        select(
            func.count(),
            _named("extension_installed"),
            _named("extension_updated"),
            _named("extension_connected"),
            _named("ext_error"),
        ).where(ExtEvent.created_at >= since)
    )
    events, installs, updates, connects, errors = period.one()
    return ExtOverview(
        active_1d=active_1d,
        active_7d=active_7d,
        active_30d=active_30d,
        events=events,
        installs=installs,
        updates=updates,
        connects=connects,
        errors=errors,
    )


async def versions(db: AsyncSession, since: datetime) -> list[ExtVersionRow]:
    """Which versions people are on: each user counted at the version they used last."""
    latest = (
        select(ExtEvent.user_id, ExtEvent.version)
        .where(ExtEvent.created_at >= since, ExtEvent.version.isnot(None))
        .distinct(ExtEvent.user_id)
        .order_by(ExtEvent.user_id, ExtEvent.created_at.desc())
        .subquery()
    )
    rows = await db.execute(
        select(latest.c.version, func.count())
        .group_by(latest.c.version)
        .order_by(func.count().desc())
    )
    return [ExtVersionRow(version=version, users=users) for version, users in rows.tuples()]


async def daily_rows(db: AsyncSession, since: datetime) -> list[ExtDayRow]:
    day = func.date_trunc("day", ExtEvent.created_at)
    rows = await db.execute(
        select(
            day,
            func.count(distinct(ExtEvent.user_id)),
            _named("autofill_filled"),
            _named("answer_saved") + _named("autofill_learned"),
            _named("suggestion_used"),
            _named("ai_succeeded"),
            _named("job_scored"),
        )
        .where(ExtEvent.created_at >= since)
        .group_by(day)
        .order_by(day)
    )
    return [
        ExtDayRow(
            day=at.strftime("%Y-%m-%d"),
            active_users=users,
            autofill_filled=filled,
            answers_saved=saved,
            suggestions_used=used,
            ai_answers=ai,
            jobs_scored=scored,
        )
        for at, users, filled, saved, used, ai, scored in rows.tuples()
    ]


async def funnel(db: AsyncSession, since: datetime) -> list[ExtFunnelStep]:
    names = [name for name, _ in FUNNEL]
    rows = await db.execute(
        select(ExtEvent.name, func.count(distinct(ExtEvent.user_id)), func.count())
        .where(ExtEvent.created_at >= since, ExtEvent.name.in_(names))
        .group_by(ExtEvent.name)
    )
    found = {name: (users, events) for name, users, events in rows.tuples()}
    return [
        ExtFunnelStep(
            step=name,
            label=label,
            users=found.get(name, (0, 0))[0],
            events=found.get(name, (0, 0))[1],
        )
        for name, label in FUNNEL
    ]


async def features(db: AsyncSession, since: datetime) -> list[ExtFeatureRow]:
    rows = await db.execute(
        select(ExtEvent.name, func.count(), func.count(distinct(ExtEvent.user_id)))
        .where(ExtEvent.created_at >= since)
        .group_by(ExtEvent.name)
        .order_by(func.count().desc())
    )
    return [ExtFeatureRow(name=name, events=n, users=u) for name, n, u in rows.tuples()]


async def _by_prop(db: AsyncSession, since: datetime, name: str, prop: str) -> list[ExtCountRow]:
    label = func.coalesce(ExtEvent.props[prop].astext, "unknown")
    rows = await db.execute(
        select(label, func.count())
        .where(ExtEvent.created_at >= since, ExtEvent.name == name)
        .group_by(label)
        .order_by(func.count().desc())
    )
    return [ExtCountRow(label=value, events=n) for value, n in rows.tuples()]


async def ai_stats(db: AsyncSession, since: datetime, purpose: str) -> ExtAiStats:
    counts = await db.execute(
        select(
            _named("ai_requested"),
            _named("ai_succeeded"),
            _named("ai_failed"),
            func.count().filter(
                ExtEvent.name == "ai_failed", ExtEvent.props["reason"].astext == "limit"
            ),
        ).where(ExtEvent.created_at >= since)
    )
    requested, succeeded, failed, limit_hits = counts.one()
    calls = await db.execute(
        select(
            func.count().filter(~AiCall.own_key),
            func.count().filter(AiCall.own_key),
            func.coalesce(func.sum(AiCall.input_tokens), 0),
            func.coalesce(func.sum(AiCall.output_tokens), 0),
        ).where(AiCall.created_at >= since, AiCall.purpose == purpose, AiCall.ok)
    )
    paid, own, tokens_in, tokens_out = calls.one()
    return ExtAiStats(
        requested=requested,
        succeeded=succeeded,
        failed=failed,
        limit_hits=limit_hits,
        by_mode=await _by_prop(db, since, "ai_requested", "mode"),
        failures=await _by_prop(db, since, "ai_failed", "reason"),
        paid_calls=paid,
        own_key_calls=own,
        input_tokens=int(tokens_in or 0),
        output_tokens=int(tokens_out or 0),
    )


async def sites(db: AsyncSession, since: datetime, limit: int = 30) -> list[ExtSiteRow]:
    offered = _named("autofill_offered")
    rows = await db.execute(
        select(
            ExtEvent.host,
            func.count(distinct(ExtEvent.user_id)),
            offered,
            _named("autofill_filled"),
            _named("autofill_failed"),
            _named("suggestion_used"),
            _named("ai_succeeded"),
        )
        .where(ExtEvent.created_at >= since, ExtEvent.host.isnot(None))
        .group_by(ExtEvent.host)
        .order_by(func.count(distinct(ExtEvent.user_id)).desc(), offered.desc())
        .limit(limit)
    )
    return [
        ExtSiteRow(
            host=host,
            users=users,
            offered=n_offered,
            filled=filled,
            failed=n_failed,
            suggestions_used=used,
            ai_answers=ai,
            fill_rate_pct=round(filled * 100 / n_offered) if n_offered else 0,
        )
        for host, users, n_offered, filled, n_failed, used, ai in rows.tuples()
    ]


async def errors(db: AsyncSession, since: datetime, limit: int = 30) -> list[ExtErrorRow]:
    where = func.coalesce(ExtEvent.props["where"].astext, "unknown")
    rows = await db.execute(
        select(
            where,
            ExtEvent.version,
            func.count(),
            func.count(distinct(ExtEvent.user_id)),
            func.max(ExtEvent.created_at),
        )
        .where(ExtEvent.created_at >= since, ExtEvent.name == "ext_error")
        .group_by(where, ExtEvent.version)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [
        ExtErrorRow(where=w, version=v, events=n, users=u, last_seen=last)
        for w, v, n, u, last in rows.tuples()
    ]


async def timeline(db: AsyncSession, user_id: uuid.UUID, limit: int = 100) -> list[ExtEventRead]:
    """One user's latest events, newest first."""
    rows = await db.execute(
        select(ExtEvent)
        .where(ExtEvent.user_id == user_id)
        .order_by(ExtEvent.created_at.desc(), ExtEvent.id.desc())
        .limit(limit)
    )
    return [
        ExtEventRead(
            at=event.created_at,
            name=event.name,
            host=event.host,
            count=event.count,
            version=event.version,
            props=event.props,
        )
        for event in rows.scalars()
    ]


# ── The first admin page's figures (kept while the panel moves to `ExtAnalytics`) ──


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
    return ExtEventTotals(
        autofill_offered=offered,
        autofill_filled=filled,
        autofill_failed=counts.get("autofill_failed", 0),
        autofill_learned=counts.get("autofill_learned", 0),
        job_scored=counts.get("job_scored", 0),
        panel_opened=counts.get("panel_opened", 0),
        apply_clicked=counts.get("apply_clicked", 0),
        fill_rate_pct=round(filled * 100 / offered) if offered else 0,
    )


async def daily(db: AsyncSession, since: datetime) -> list[ExtEventDay]:
    day = func.date_trunc("day", ExtEvent.created_at)
    rows = await db.execute(
        select(
            day,
            _named("autofill_offered"),
            _named("autofill_filled"),
            _named("job_scored"),
            _named("apply_clicked"),
        )
        .where(ExtEvent.created_at >= since)
        .group_by(day)
        .order_by(day)
    )
    return [
        ExtEventDay(
            day=at.strftime("%Y-%m-%d"),
            autofill_offered=offered,
            autofill_filled=filled,
            job_scored=scored,
            apply_clicked=applied,
        )
        for at, offered, filled, scored, applied in rows.tuples()
    ]


async def top_sites(db: AsyncSession, since: datetime, limit: int = 20) -> list[ExtEventSiteRow]:
    offered = _named("autofill_offered")
    rows = await db.execute(
        select(ExtEvent.host, offered, _named("autofill_filled"))
        .where(ExtEvent.created_at >= since, ExtEvent.host.isnot(None))
        .group_by(ExtEvent.host)
        .having(offered > 0)
        .order_by(offered.desc())
        .limit(limit)
    )
    return [
        ExtEventSiteRow(
            host=host,
            offered=n_offered,
            filled=filled,
            fill_rate_pct=round(filled * 100 / n_offered) if n_offered else 0,
        )
        for host, n_offered, filled in rows.tuples()
    ]
