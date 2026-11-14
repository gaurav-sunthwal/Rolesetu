"""Database helpers for extension installs and their steps before connecting."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    and_,
    case,
    delete,
    exists,
    func,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.ext_events.models import ExtEvent
from backend.modules.ext_events.schemas import ExtEventRead
from backend.modules.ext_installs.models import ExtInstall, ExtInstallEvent
from backend.modules.ext_installs.schemas import (
    InstallGroupRow,
    InstallRow,
    InstallStats,
    InstallStep,
)

KEEP_FOR = timedelta(days=90)
# An address that made this many installs in the period is likely one machine.
CROWDED_FROM = 3
_USE = ("job_detected", "form_detected")


# ── Writing ───────────────────────────────────────────────────────────────────


async def get(db: AsyncSession, install_id: str) -> ExtInstall | None:
    result = await db.execute(select(ExtInstall).where(ExtInstall.install_id == install_id))
    return result.scalar_one_or_none()


async def count_new_by_client(db: AsyncSession, client_hash: str, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ExtInstall)
        .where(ExtInstall.client_hash == client_hash, ExtInstall.created_at > since)
    )
    return result.scalar_one()


async def count_events(db: AsyncSession, install_id: str, since: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ExtInstallEvent)
        .where(ExtInstallEvent.install_id == install_id, ExtInstallEvent.created_at > since)
    )
    return result.scalar_one()


async def save(db: AsyncSession, install_id: str, info: dict[str, Any], now: datetime) -> None:
    """Creates the install, or brings what is known about it up to date. Only
    what this sender knows is written: the website knows less than the extension."""
    known = {key: value for key, value in info.items() if value is not None}
    statement = insert(ExtInstall).values(
        id=uuid.uuid4(), install_id=install_id, last_seen_at=now, **known
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[ExtInstall.install_id],
            set_={"last_seen_at": now, **{key: statement.excluded[key] for key in known}},
        )
    )


async def insert_events(db: AsyncSession, install_id: str, events: list[dict[str, Any]]) -> None:
    if events:
        await db.execute(
            insert(ExtInstallEvent)
            .values([{"id": uuid.uuid4(), "install_id": install_id, **event} for event in events])
            .on_conflict_do_nothing(index_elements=["client_id"])
        )
    cutoff = datetime.now(UTC) - KEEP_FOR
    await db.execute(delete(ExtInstallEvent).where(ExtInstallEvent.created_at < cutoff))
    await db.execute(
        delete(ExtInstall).where(ExtInstall.user_id.is_(None), ExtInstall.last_seen_at < cutoff)
    )


async def link_to_user(
    db: AsyncSession, install_id: str, user_id: uuid.UUID, now: datetime
) -> None:
    """The install is now connected to this account. An install already linked to
    another account is left alone."""
    statement = insert(ExtInstall).values(
        id=uuid.uuid4(), install_id=install_id, user_id=user_id, connected_at=now, last_seen_at=now
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[ExtInstall.install_id],
            set_={
                "user_id": user_id,
                "connected_at": func.coalesce(ExtInstall.connected_at, now),
                "last_seen_at": now,
            },
            where=or_(ExtInstall.user_id.is_(None), ExtInstall.user_id == user_id),
        )
    )


async def mark_uninstalled(db: AsyncSession, install_id: str, now: datetime) -> datetime | None:
    """Records the uninstall. Returns when the install was made, the first time
    only: None for an unknown install or one already recorded as removed."""
    result = await db.execute(
        update(ExtInstall)
        .where(ExtInstall.install_id == install_id, ExtInstall.uninstalled_at.is_(None))
        .values(uninstalled_at=now, last_seen_at=now)
        .returning(ExtInstall.created_at)
        .execution_options(synchronize_session=False)
    )
    return result.scalar_one_or_none()


# ── Reading (admin) ───────────────────────────────────────────────────────────


def _did(*names: str) -> ColumnElement[bool]:
    return exists().where(
        ExtInstallEvent.install_id == ExtInstall.install_id, ExtInstallEvent.name.in_(names)
    )


def _used() -> ColumnElement[bool]:
    after_connecting = exists().where(
        ExtInstall.user_id.is_not(None),
        ExtEvent.user_id == ExtInstall.user_id,
        ExtEvent.name.in_(_USE),
    )
    return or_(_did(*_USE), after_connecting)


_CONNECTED = ExtInstall.connected_at.is_not(None)

# What each step means, in the order a new user goes through them.
STEPS: list[tuple[str, str, ColumnElement[bool]]] = [
    ("installed", "Installed", true()),
    ("setup_opened", "Extension opened the setup page", _did("setup_opened")),
    ("setup_page_seen", "Setup page loaded", _did("setup_page_seen")),
    ("popup_opened", "Clicked the extension's icon", _did("popup_opened")),
    ("signup_started", "Started signing up or in", _did("signup_started")),
    ("signed_in", "Signed in", or_(_did("signed_in"), _CONNECTED)),
    ("connected", "Extension connected", _CONNECTED),
    ("used", "Used it on a job page", _used()),
]


async def _group(
    db: AsyncSession, since: datetime, column: Any, limit: int = 12
) -> list[InstallGroupRow]:
    label = func.coalesce(column, "unknown")
    rows = await db.execute(
        select(label, func.count(), func.count().filter(_CONNECTED))
        .where(ExtInstall.created_at >= since)
        .group_by(label)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [InstallGroupRow(label=str(name), installs=n, connected=c) for name, n, c in rows]


def _reached(names: set[str], connected: bool) -> str:
    if names & set(_USE):
        return "Used it on a job page"
    if connected:
        return "Extension connected"
    furthest = "Installed"
    for step, label, _ in STEPS[1:6]:
        if step in names:
            furthest = label
    if "connect_failed" in names:
        return "Signed in, connecting failed"
    if "sign_in_failed" in names and "signed_in" not in names:
        return "Sign-in failed"
    return furthest


async def stats(db: AsyncSession, since: datetime, hours: int, limit: int = 100) -> InstallStats:
    in_period = ExtInstall.created_at >= since
    # How many installs in the period came from each install's address (itself included).
    same_address = case(
        (ExtInstall.client_hash.is_(None), 1),
        else_=func.count().over(partition_by=ExtInstall.client_hash),
    )
    crowd = select(ExtInstall.id, same_address.label("same")).where(in_period).subquery()

    totals = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(_CONNECTED),
                func.count().filter(ExtInstall.uninstalled_at.is_not(None)),
                func.count().filter(
                    and_(
                        ~_CONNECTED,
                        ~exists().where(
                            ExtInstallEvent.install_id == ExtInstall.install_id,
                            ExtInstallEvent.name.not_in(
                                ("extension_installed", "extension_uninstalled", "ext_error")
                            ),
                        ),
                    )
                ),
                func.count().filter(ExtInstall.automated.is_(True)),
                func.count().filter(crowd.c.same >= CROWDED_FROM),
                *(func.count().filter(condition) for _, _, condition in STEPS),
            )
            .select_from(ExtInstall)
            .join(crowd, crowd.c.id == ExtInstall.id)
            .where(in_period)
        )
    ).one()
    installs, connected, uninstalled, silent, automated, crowded, *reached = totals

    reason = func.coalesce(ExtInstallEvent.props["reason"].astext, "none")
    reasons = await db.execute(
        select(reason, func.count())
        .where(ExtInstallEvent.name == "uninstall_reason", ExtInstallEvent.created_at >= since)
        .group_by(reason)
        .order_by(func.count().desc())
    )

    recent_rows = (
        await db.execute(
            select(ExtInstall, crowd.c.same)
            .join(crowd, crowd.c.id == ExtInstall.id)
            .order_by(ExtInstall.created_at.desc())
            .limit(limit)
        )
    ).all()
    ids = [install.install_id for install, _ in recent_rows]
    names: dict[str, set[str]] = {install_id: set() for install_id in ids}
    if ids:
        for install_id, name in await db.execute(
            select(ExtInstallEvent.install_id, ExtInstallEvent.name)
            .where(ExtInstallEvent.install_id.in_(ids))
            .distinct()
        ):
            names[install_id].add(name)
        users = [install.user_id for install, _ in recent_rows if install.user_id]
        used_users = set(
            (
                await db.execute(
                    select(ExtEvent.user_id)
                    .where(ExtEvent.user_id.in_(users), ExtEvent.name.in_(_USE))
                    .distinct()
                )
            ).scalars()
            if users
            else []
        )
        for install, _ in recent_rows:
            if install.user_id in used_users:
                names[install.install_id].add("job_detected")

    return InstallStats(
        hours=hours,
        installs=installs,
        connected=connected,
        uninstalled=uninstalled,
        silent=silent,
        automated=automated,
        crowded=crowded,
        funnel=[
            InstallStep(step=step, label=label, installs=count)
            for (step, label, _), count in zip(STEPS, reached, strict=True)
        ],
        by_os=await _group(db, since, ExtInstall.os),
        by_browser=await _group(db, since, ExtInstall.browser),
        by_language=await _group(db, since, ExtInstall.language),
        by_timezone=await _group(db, since, ExtInstall.timezone, limit=15),
        by_version=await _group(db, since, ExtInstall.version),
        uninstall_reasons=[
            InstallGroupRow(label=str(reason), installs=n, connected=0) for reason, n in reasons
        ],
        recent=[
            InstallRow(
                install_id=install.install_id,
                installed_at=install.created_at,
                last_seen_at=install.last_seen_at,
                version=install.version,
                browser=install.browser,
                os=install.os,
                language=install.language,
                timezone=install.timezone,
                automated=install.automated,
                same_address=max(int(same) - 1, 0),
                reached=_reached(names[install.install_id], install.connected_at is not None),
                user_id=str(install.user_id) if install.user_id else None,
                uninstalled_at=install.uninstalled_at,
            )
            for install, same in recent_rows
        ],
    )


async def journey(db: AsyncSession, install_id: str, limit: int = 200) -> list[ExtEventRead]:
    """Everything this install did, newest first: its steps before connecting and,
    once connected, the account's extension events."""
    install = await get(db, install_id)
    if install is None:
        return []
    before = select(
        ExtInstallEvent.created_at,
        ExtInstallEvent.name,
        ExtInstallEvent.host,
        ExtInstallEvent.count,
        ExtInstallEvent.version,
        ExtInstallEvent.props,
    ).where(ExtInstallEvent.install_id == install_id)
    queries = [before]
    if install.user_id is not None:
        queries.append(
            select(
                ExtEvent.created_at,
                ExtEvent.name,
                ExtEvent.host,
                ExtEvent.count,
                ExtEvent.version,
                ExtEvent.props,
            ).where(ExtEvent.user_id == install.user_id)
        )
    rows: list[Any] = []
    for query in queries:
        rows.extend(
            (await db.execute(query.order_by(query.selected_columns[0].desc()).limit(limit))).all()
        )
    rows.sort(key=lambda row: row[0], reverse=True)
    return [
        ExtEventRead(at=at, name=name, host=host, count=count, version=version, props=props)
        for at, name, host, count, version, props in rows[:limit]
    ]
