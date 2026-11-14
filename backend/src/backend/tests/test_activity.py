"""The yearly activity grid on the dashboard: actions per day in the user's own time
zone, and streaks, through the API and database."""

import uuid
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import text

from backend.db.session import get_sessionmaker
from backend.modules.activity import service
from backend.tests.conftest import ClientFactory

URL = "/api/v1/activity/me"
INDIA = ZoneInfo("Asia/Kolkata")


def test_a_streak_is_days_in_a_row_and_today_does_not_break_it_yet() -> None:
    assert service.streaks([True, True, False, True, True, True]).model_dump() == {
        "current": 3,
        "longest": 3,
        "active_days": 5,
    }
    # Nothing yet today: yesterday's run still counts.
    assert service.streaks([True, True, True, False]).current == 3
    # Nothing yesterday either: the streak is over.
    assert service.streaks([True, True, False, False]).current == 0
    assert service.streaks([]).model_dump() == {"current": 0, "longest": 0, "active_days": 0}


async def user_id_of(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])


async def applied(client: AsyncClient, *, days_ago: int, count: int = 1) -> None:
    user_id = await user_id_of(client)
    # Noon on that day in India, the time zone the test asks for.
    local_day = datetime.now(INDIA).date() - timedelta(days=days_ago)
    at = datetime.combine(local_day, time(12, 0), INDIA)
    async with get_sessionmaker()() as db:
        for _ in range(count):
            await db.execute(
                text(
                    "INSERT INTO applications (id, user_id, role, company, status, created_at)"
                    " VALUES (:i, :u, 'Engineer', 'Acme', 'applied', :at)"
                ),
                {"i": uuid.uuid4(), "u": user_id, "at": at},
            )
            await db.execute(
                text(
                    "INSERT INTO ext_events (id, user_id, name, created_at)"
                    " VALUES (:i, :u, 'autofill_filled', :at)"
                ),
                {"i": uuid.uuid4(), "u": user_id, "at": at},
            )
        await db.commit()


def day_of(body: dict[str, Any], days_ago: int) -> dict[str, Any]:
    return dict(body["days"][-1 - days_ago])


async def test_the_year_counts_each_day_and_the_streaks(client: AsyncClient) -> None:
    await applied(client, days_ago=0, count=2)
    await applied(client, days_ago=1)
    await applied(client, days_ago=3)

    response = await client.get(URL, params={"tz": "Asia/Kolkata"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["timezone"] == "Asia/Kolkata"
    assert len(body["days"]) == service.DAYS_SHOWN
    assert body["days"][-1]["date"] == body["end"] and body["days"][0]["date"] == body["start"]

    today = day_of(body, 0)
    assert today["applications"] == 2 and today["extension"] == 2
    assert day_of(body, 2)["applications"] == 0
    assert body["totals"]["applications"] == 4
    assert body["streaks"] == {"current": 2, "longest": 2, "active_days": 3}


async def test_an_unknown_time_zone_falls_back_to_utc(client: AsyncClient) -> None:
    body = (await client.get(URL, params={"tz": "Mars/Olympus'; DROP TABLE users;--"})).json()
    assert body["timezone"] == "UTC"


async def test_one_users_activity_is_not_anothers(make_client: ClientFactory) -> None:
    busy, other = make_client(), make_client()
    await applied(busy, days_ago=0, count=3)
    body = (await other.get(URL)).json()
    assert body["totals"]["applications"] == 0
    assert body["streaks"]["active_days"] == 0
