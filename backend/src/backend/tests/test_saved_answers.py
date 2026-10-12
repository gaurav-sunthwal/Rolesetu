from httpx import AsyncClient

from backend.tests.conftest import ClientFactory


async def test_upsert_list_and_delete(client: AsyncClient) -> None:
    created = await client.put("/api/v1/saved-answers/notice_period", json={"answer": "30 days"})
    assert created.status_code == 200

    updated = await client.put("/api/v1/saved-answers/notice_period", json={"answer": "15 days"})
    assert updated.json()["answer"] == "15 days"

    listed = (await client.get("/api/v1/saved-answers")).json()
    assert [(a["question_key"], a["answer"]) for a in listed] == [("notice_period", "15 days")]

    assert (await client.delete("/api/v1/saved-answers/notice_period")).status_code == 204
    assert (await client.get("/api/v1/saved-answers")).json() == []


async def test_key_format_is_enforced(client: AsyncClient) -> None:
    response = await client.put("/api/v1/saved-answers/Bad Key!", json={"answer": "x"})
    assert response.status_code == 422


async def test_answers_are_private_to_their_owner(make_client: ClientFactory) -> None:
    alice, bob = make_client(), make_client()
    await alice.put("/api/v1/saved-answers/expected_ctc", json={"answer": "confidential"})
    assert (await bob.get("/api/v1/saved-answers")).json() == []
