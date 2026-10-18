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


LEARN = "/api/v1/extension/learned-answers"


async def test_learning_saves_new_answers_and_reports_what_changed(client: AsyncClient) -> None:
    await client.put("/api/v1/saved-answers/notice_period", json={"answer": "30 days"})

    learned = await client.post(
        LEARN,
        json={
            "answers": [
                {"question_key": "date_of_birth", "answer": "1998-05-12"},
                {"question_key": "notice_period", "answer": "60 days"},
                {"question_key": "q_how_did_you_hear_about_us", "answer": "LinkedIn"},
            ]
        },
    )
    assert learned.status_code == 200
    assert learned.json() == [
        {"question_key": "date_of_birth", "previous": None},
        {"question_key": "notice_period", "previous": "30 days"},
        {"question_key": "q_how_did_you_hear_about_us", "previous": None},
    ]

    autofill = (await client.get("/api/v1/extension/autofill")).json()
    assert autofill["saved_answers"]["date_of_birth"] == "1998-05-12"
    assert autofill["saved_answers"]["notice_period"] == "60 days"


async def test_learning_the_same_answer_again_changes_nothing(client: AsyncClient) -> None:
    body = {"answers": [{"question_key": "gender", "answer": "Female"}]}
    assert (await client.post(LEARN, json=body)).json() == [
        {"question_key": "gender", "previous": None}
    ]
    assert (await client.post(LEARN, json=body)).json() == []


async def test_forgetting_a_learned_answer(client: AsyncClient) -> None:
    await client.post(LEARN, json={"answers": [{"question_key": "gender", "answer": "Male"}]})
    assert (await client.delete(f"{LEARN}/gender")).status_code == 204
    assert (await client.get("/api/v1/saved-answers")).json() == []


async def test_learning_rejects_bad_keys_and_long_answers(client: AsyncClient) -> None:
    bad_key = {"answers": [{"question_key": "Date Of Birth", "answer": "x"}]}
    assert (await client.post(LEARN, json=bad_key)).status_code == 422
    essay = {"answers": [{"question_key": "q_about_you", "answer": "x" * 501}]}
    assert (await client.post(LEARN, json=essay)).status_code == 422
    assert (await client.post(LEARN, json={"answers": []})).status_code == 422


async def test_learned_answers_are_private_to_their_owner(make_client: ClientFactory) -> None:
    alice, bob = make_client(), make_client()
    await alice.post(
        LEARN, json={"answers": [{"question_key": "date_of_birth", "answer": "1990-01-01"}]}
    )
    assert (await bob.get("/api/v1/saved-answers")).json() == []
    # Bob forgetting the same key leaves Alice's answer alone.
    await bob.delete(f"{LEARN}/date_of_birth")
    assert len((await alice.get("/api/v1/saved-answers")).json()) == 1
