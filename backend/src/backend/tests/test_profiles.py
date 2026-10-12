from typing import Any

from httpx import AsyncClient

from backend.tests.conftest import ClientFactory

PROFILE: dict[str, Any] = {
    "full_name": "Asha Rao",
    "headline": "Frontend engineer",
    "links": {"github": "https://github.com/asha"},
    "skills": [{"id": "s1", "name": "React", "level": "advanced"}],
    "experience": [
        {
            "id": "e1",
            "title": "Engineer",
            "company": "Acme",
            "start": "2022-01",
            "end": None,
            "description": "Built the admin app in React.",
        }
    ],
}


async def test_new_user_gets_an_empty_profile(client: AsyncClient) -> None:
    response = await client.get("/api/v1/profile/me")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 0
    assert body["completeness"] == 0
    assert body["skills"] == []


async def test_save_and_read_back(client: AsyncClient) -> None:
    saved = await client.put("/api/v1/profile/me", json=PROFILE)
    assert saved.status_code == 200
    assert saved.json()["version"] == 1

    body = (await client.get("/api/v1/profile/me")).json()
    assert body["full_name"] == "Asha Rao"
    assert body["experience"][0]["company"] == "Acme"
    # name 10 + headline 10 + one skill 10 + experience 25 + a link 10
    assert body["completeness"] == 65


async def test_version_only_bumps_when_something_changed(client: AsyncClient) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    same = await client.put("/api/v1/profile/me", json=PROFILE)
    assert same.json()["version"] == 1

    changed = await client.put("/api/v1/profile/me", json={**PROFILE, "headline": "Staff engineer"})
    assert changed.json()["version"] == 2


async def test_invalid_dates_are_rejected(client: AsyncClient) -> None:
    bad = {**PROFILE, "experience": [{**PROFILE["experience"][0], "start": "Jan 2022"}]}
    assert (await client.put("/api/v1/profile/me", json=bad)).status_code == 422


async def test_profiles_are_private_to_their_owner(make_client: ClientFactory) -> None:
    alice, bob = make_client(), make_client()
    await alice.put("/api/v1/profile/me", json=PROFILE)
    assert (await bob.get("/api/v1/profile/me")).json()["full_name"] is None
