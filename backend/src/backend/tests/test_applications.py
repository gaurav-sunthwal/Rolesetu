from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from backend.tests.conftest import ClientFactory

BASE = "/api/v1/applications"


async def _create(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    payload = {"role": "Frontend Engineer", "company": "Acme", **overrides}
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_create_records_the_first_event(client: AsyncClient) -> None:
    created = await _create(client)
    assert created["status"] == "saved"
    assert created["applied_at"] is None
    assert [event["type"] for event in created["events"]] == ["saved"]


async def test_status_change_adds_an_event_and_sets_applied_at(client: AsyncClient) -> None:
    created = await _create(client)
    updated = await client.patch(f"{BASE}/{created['id']}", json={"status": "applied"})
    body = updated.json()
    assert body["status"] == "applied"
    assert body["applied_at"] is not None
    assert {event["type"] for event in body["events"]} == {"saved", "applied"}

    # Editing a note is not a status change, so no new event.
    noted = await client.patch(f"{BASE}/{created['id']}", json={"notes": "Referred by Sam"})
    assert noted.json()["notes"] == "Referred by Sam"
    assert len(noted.json()["events"]) == 2


async def test_filter_search_and_pagination(client: AsyncClient) -> None:
    for index in range(3):
        await _create(client, role=f"Engineer {index}", company="Acme", status="applied")
    await _create(client, role="Designer", company="Globex")

    applied = (await client.get(BASE, params={"status": "applied"})).json()
    assert len(applied["items"]) == 3

    found = (await client.get(BASE, params={"q": "globex"})).json()
    assert [item["role"] for item in found["items"]] == ["Designer"]

    first = (await client.get(BASE, params={"limit": 3})).json()
    assert len(first["items"]) == 3 and first["next_cursor"]
    second = (await client.get(BASE, params={"limit": 3, "cursor": first["next_cursor"]})).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    seen = {item["id"] for item in first["items"]} | {item["id"] for item in second["items"]}
    assert len(seen) == 4


async def test_retrying_with_the_same_key_does_not_duplicate(client: AsyncClient) -> None:
    payload = {"role": "Engineer", "company": "Acme"}
    headers = {"Idempotency-Key": "retry-123"}
    first = await client.post(BASE, json=payload, headers=headers)
    second = await client.post(BASE, json=payload, headers=headers)
    assert first.json()["id"] == second.json()["id"]
    assert len((await client.get(BASE)).json()["items"]) == 1


async def test_stats_and_follow_up_flag(client: AsyncClient) -> None:
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    stale = await _create(client, status="applied", applied_at=old)
    await _create(client, status="applied")
    await _create(client, status="interview")
    await _create(client, status="rejected")
    await _create(client)

    assert stale["needs_follow_up"] is True
    stats = (await client.get(f"{BASE}/stats")).json()
    assert stats["total"] == 5
    assert stats["sent"] == 4
    assert stats["responded"] == 2
    assert stats["reply_rate"] == 0.5
    assert stats["interviews"] == 1
    assert stats["rejections"] == 1
    assert stats["follow_ups_due"] == 1


async def test_stats_for_a_new_user_have_no_reply_rate(client: AsyncClient) -> None:
    stats = (await client.get(f"{BASE}/stats")).json()
    assert stats["total"] == 0 and stats["reply_rate"] is None


async def test_delete(client: AsyncClient) -> None:
    created = await _create(client)
    assert (await client.delete(f"{BASE}/{created['id']}")).status_code == 204
    assert (await client.get(f"{BASE}/{created['id']}")).status_code == 404


async def test_applications_are_private_to_their_owner(make_client: ClientFactory) -> None:
    alice, bob = make_client(), make_client()
    created = await _create(alice)
    url = f"{BASE}/{created['id']}"

    assert (await bob.get(url)).status_code == 404
    assert (await bob.patch(url, json={"status": "offer"})).status_code == 404
    assert (await bob.delete(url)).status_code == 404
    assert (await bob.get(BASE)).json()["items"] == []
    assert (await alice.get(url)).json()["status"] == "saved"
