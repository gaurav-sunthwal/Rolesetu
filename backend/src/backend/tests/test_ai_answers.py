"""Answers the model writes on request: checked against the user's data, and paid
for with the plan's AI credits, through the API and database. The model itself is
faked."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from backend.ai import answer_writer, llm_client
from backend.ai.answer_writer import WrittenAnswer
from backend.db.session import get_sessionmaker
from backend.modules.credits import service as credits
from backend.modules.pitch import ai_answers
from backend.tests.conftest import ClientFactory

URL = "/api/v1/extension/ai-answers"
BODY = {
    "mode": "write",
    "question": "What interests you about working for this company?",
    "company": "Encord",
    "role": "Frontend Engineer",
    "job_text": "We build data tooling with React and TypeScript.",
}
FREE = credits.CREDITS_PER_MONTH["free"]
PRO = credits.CREDITS_PER_MONTH["pro"]


class FakeModel:
    def __init__(self, answer: str, *, fails: bool = False) -> None:
        self.answer = answer
        self.fails = fails
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, prompt: str, **kwargs: Any) -> WrittenAnswer:
        self.calls.append({"prompt": prompt, **kwargs})
        if self.fails:
            raise llm_client.LLMUnavailableError()
        return WrittenAnswer(answer=self.answer)


@pytest.fixture(autouse=True)
async def _needs_tables() -> None:
    async with get_sessionmaker()() as db:
        found = await db.execute(text("select to_regclass('public.credit_usage')"))
        if found.scalar_one() is None:
            pytest.skip("Apply migration f9b1d3e5a7c2 to run these tests.")


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    fake = FakeModel(
        "Encord builds data tooling with React, which is what I want to work on."
        " I have 7 years of Kubernetes at Google."
    )
    monkeypatch.setattr(answer_writer, "write_answer", fake)
    return fake


async def user_id_of(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])


async def set_used(client: AsyncClient, used: int) -> uuid.UUID:
    user_id = await user_id_of(client)
    period = credits.period_of(datetime.now(UTC))
    async with get_sessionmaker()() as db:
        await db.execute(
            text(
                "INSERT INTO credit_usage (user_id, period, used) VALUES (:u, :p, :n)"
                " ON CONFLICT (user_id, period) DO UPDATE SET used = :n"
            ),
            {"u": user_id, "p": period, "n": used},
        )
        await db.commit()
    return user_id


async def used_of(client: AsyncClient) -> int:
    response = await client.get("/api/v1/credits/me")
    assert response.status_code == 200
    return int(response.json()["used"])


async def make_pro(client: AsyncClient) -> None:
    """A paid month, as the billing module writes it."""
    user_id = await user_id_of(client)
    now = datetime.now(UTC)
    async with get_sessionmaker()() as db:
        await db.execute(
            text(
                "INSERT INTO billing_orders (id, user_id, razorpay_order_id, plan, amount,"
                " currency, status, paid_at, pro_starts_at, pro_ends_at)"
                " VALUES (:id, :u, :o, 'pro_month', 19900, 'INR', 'paid', :now, :start, :end)"
            ),
            {
                "id": uuid.uuid4(),
                "u": user_id,
                "o": f"order_test{uuid.uuid4().hex[:12]}",
                "now": now,
                "start": now - timedelta(days=1),
                "end": now + timedelta(days=29),
            },
        )
        await db.commit()


def test_a_sentence_with_a_claim_nothing_backs_is_taken_out() -> None:
    sources = "Skills: React, TypeScript. Built ChatFlow for 500+ users."
    text_, removed = ai_answers.keep_supported(
        "I built ChatFlow for 500+ users with React. I also scaled Kafka to 10M events.",
        sources,
    )
    assert text_ == "I built ChatFlow for 500+ users with React."
    assert "10M" in removed and "Kafka" in removed


async def test_an_answer_is_written_checked_and_spends_one_credit(
    client: AsyncClient, model: FakeModel
) -> None:
    response = await client.post(URL, json=BODY)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "Encord builds data tooling with React, which is what I want to work on."
    assert set(body["removed"]) >= {"7", "Kubernetes"}
    assert body["usage"] == {"left": FREE - 1, "limit": FREE}
    # The page's words go to the model only as data, marked off from the rules.
    assert "JOB:\n<<<\nCompany: Encord" in model.calls[0]["prompt"]
    assert await used_of(client) == 1

    usage = await client.get("/api/v1/extension/ai-answers/usage")
    assert usage.json() == {"left": FREE - 1, "limit": FREE}


async def test_free_credits_run_out_and_the_model_is_not_called(
    client: AsyncClient, model: FakeModel
) -> None:
    await set_used(client, FREE)
    response = await client.post(URL, json=BODY)
    assert response.status_code == 402
    assert f"{FREE} free AI credits" in response.json()["detail"]
    assert "upgrade to Pro" in response.json()["detail"]
    assert model.calls == []
    assert await used_of(client) == FREE


async def test_pro_gets_its_larger_allowance(client: AsyncClient, model: FakeModel) -> None:
    await set_used(client, FREE)
    await make_pro(client)
    response = await client.post(URL, json=BODY)
    assert response.status_code == 200, response.text
    assert response.json()["usage"] == {"left": PRO - FREE - 1, "limit": PRO}

    await set_used(client, PRO)
    blocked = await client.post(URL, json=BODY)
    assert blocked.status_code == 402
    assert "upgrade" not in blocked.json()["detail"]


async def test_a_failed_model_call_gives_the_credit_back(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await set_used(client, 3)
    failing = FakeModel("", fails=True)
    monkeypatch.setattr(answer_writer, "write_answer", failing)
    response = await client.post(URL, json=BODY)
    assert response.status_code == 503
    assert "credit was not used" in response.json()["detail"]
    assert len(failing.calls) == 1
    assert await used_of(client) == 3


async def test_nothing_truthful_to_say_is_an_error_and_costs_nothing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(answer_writer, "write_answer", FakeModel("My notice period is 30 days."))
    response = await client.post(URL, json={**BODY, "question": "Notice period?"})
    assert response.status_code == 422
    assert "Please type your answer" in response.json()["detail"]
    assert await used_of(client) == 0


async def test_improving_needs_something_to_improve(client: AsyncClient, model: FakeModel) -> None:
    response = await client.post(URL, json={**BODY, "mode": "improve", "current": "  "})
    assert response.status_code == 422
    assert model.calls == []
    assert await used_of(client) == 0


async def test_parallel_requests_never_spend_past_the_limit(
    client: AsyncClient, model: FakeModel
) -> None:
    await set_used(client, FREE - 3)
    responses = await asyncio.gather(*(client.post(URL, json=BODY) for _ in range(10)))
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] * 3 + [402] * 7
    assert await used_of(client) == FREE


async def test_one_users_credits_are_not_anothers(
    make_client: ClientFactory, model: FakeModel
) -> None:
    spender, other = make_client(), make_client()
    await set_used(spender, FREE)
    assert (await other.post(URL, json=BODY)).status_code == 200
    assert await used_of(other) == 1
    assert await used_of(spender) == FREE


async def test_a_form_answer_asks_a_fast_model_without_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured: the default model took over 45s on one answer, gemini-2.5-flash
    without thinking 2s. Someone is waiting on this one."""
    asked: list[tuple[str, str, bool, float | None]] = []

    async def call_once(
        key: str,
        model: str,
        prompt: str,
        schema: object,
        system: str | None,
        timeout: float | None = None,
        thinking: bool = True,
    ) -> llm_client._Answer[WrittenAnswer]:
        asked.append((key, model, thinking, timeout))
        return llm_client._Answer(
            parsed=WrittenAnswer(answer="Hi."),
            model=model,
            key=key,
            input_tokens=1,
            output_tokens=1,
        )

    monkeypatch.setattr(llm_client, "_call_once", call_once)
    monkeypatch.setattr(llm_client, "_cooling_until", {})
    monkeypatch.setattr(llm_client, "_candidate_keys", lambda: ["server-key"])
    await answer_writer.write_answer("prompt")
    assert asked == [("server-key", "gemini-2.5-flash", False, answer_writer.TIMEOUT_SECONDS)]
