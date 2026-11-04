"""Every model call is counted: what it was for, who asked, from where, and
what it cost. The admin panel reads these counts back.
"""

import uuid
from typing import Any

import pytest
from google import genai
from google.genai import errors
from httpx import AsyncClient
from pydantic import BaseModel

from backend.ai import llm_client
from backend.ai.llm_client import LLMUnavailableError, generate_structured
from backend.core.config import get_settings
from backend.modules.ai_calls import service as ai_calls
from backend.tests.conftest import ClientFactory
from backend.tests.test_admin import ADMIN, admin, email_of  # noqa: F401
from backend.tests.test_llm_fallback import FakeGemini, _error


class Answer(BaseModel):
    text: str


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Each call `record` receives, with the caller it saw."""
    calls: list[dict[str, Any]] = []

    async def capture(**fields: Any) -> None:
        calls.append({**fields, "caller": ai_calls.current_caller()})

    monkeypatch.setattr(ai_calls, "record", capture)
    monkeypatch.setattr(llm_client, "wait_exponential_jitter", lambda **_: lambda *_: 0)
    monkeypatch.setattr(llm_client, "_cooling_until", {})
    monkeypatch.setattr(llm_client, "_out_of_quota_until", {})
    return calls


async def test_an_answered_call_is_counted_once_with_its_model(
    monkeypatch: pytest.MonkeyPatch, recorded: list[dict[str, Any]]
) -> None:
    FakeGemini(monkeypatch, {("k1", "primary"): _error(errors.ServerError, 503)})
    await generate_structured("hi", Answer, purpose="job-read")
    assert len(recorded) == 1
    call = recorded[0]
    assert call["purpose"] == "job-read" and call["ok"] is True
    # The fallback answered, so that is the model counted.
    assert call["model"] == "backup" and call["own_key"] is False


async def test_a_call_paid_by_the_users_key_says_so(
    monkeypatch: pytest.MonkeyPatch, recorded: list[dict[str, Any]]
) -> None:
    FakeGemini(monkeypatch, {})
    await generate_structured("hi", Answer, user_api_key="mine")
    assert recorded[0]["own_key"] is True


async def test_a_failed_call_is_counted_as_failed(
    monkeypatch: pytest.MonkeyPatch, recorded: list[dict[str, Any]]
) -> None:
    overloaded = _error(errors.ServerError, 503)
    FakeGemini(monkeypatch, {("k1", m): overloaded for m in ("primary", "backup", "last")})
    with pytest.raises(LLMUnavailableError):
        await generate_structured("hi", Answer, purpose="skill-judge")
    assert len(recorded) == 1
    assert recorded[0]["ok"] is False and recorded[0]["error"] == "ServerError"


async def test_no_key_at_all_is_counted_as_failed(
    monkeypatch: pytest.MonkeyPatch, recorded: list[dict[str, Any]]
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_api_key_1", None)
    monkeypatch.setattr(settings, "llm_api_key_2", None)
    with pytest.raises(LLMUnavailableError):
        await generate_structured("hi", Answer)
    assert recorded[0]["error"] == "NoKeyConfigured"


async def test_tokens_are_read_from_the_response(
    monkeypatch: pytest.MonkeyPatch, recorded: list[dict[str, Any]]
) -> None:
    usage = type(
        "Usage",
        (),
        {"prompt_token_count": 120, "candidates_token_count": 30, "thoughts_token_count": 10},
    )()

    class _Models:
        async def generate_content(self, **_: Any) -> object:
            return type("Response", (), {"parsed": Answer(text="ok"), "usage_metadata": usage})()

    class _Client:
        def __init__(self, api_key: str) -> None:
            self.aio = type("Aio", (), {"models": _Models()})()

    FakeGemini(monkeypatch, {})
    monkeypatch.setattr(genai, "Client", _Client)
    await generate_structured("hi", Answer)
    # Thinking is billed as output, so it is counted with the answer.
    assert recorded[0]["input_tokens"] == 120 and recorded[0]["output_tokens"] == 40


async def test_the_caller_is_whoever_wrapped_the_work(
    monkeypatch: pytest.MonkeyPatch, recorded: list[dict[str, Any]]
) -> None:
    FakeGemini(monkeypatch, {})
    user_id = uuid.uuid4()
    with ai_calls.called_by(user_id, "extension"):
        await generate_structured("hi", Answer)
    await generate_structured("hi", Answer)
    assert recorded[0]["caller"] == ai_calls.Caller(user_id=user_id, source="extension")
    # Outside the block nobody is named.
    assert recorded[1]["caller"] is None


@pytest.mark.parametrize("path", ["/ai-calls", "/ai-calls/summary"])
async def test_an_ordinary_user_cannot_see_ai_calls(client: AsyncClient, path: str) -> None:
    assert (await client.get(f"{ADMIN}{path}")).status_code == 403


async def _user_id(client: AsyncClient) -> uuid.UUID:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200
    return uuid.UUID(response.json()["id"])


@pytest.mark.records_ai_calls
async def test_an_admin_sees_each_users_calls_by_source(
    admin: AsyncClient,  # noqa: F811
    make_client: ClientFactory,
) -> None:
    someone, other = make_client(), make_client()
    someone_id, other_id = await _user_id(someone), await _user_id(other)
    made: list[tuple[uuid.UUID, ai_calls.Source]] = [
        (someone_id, "extension"),
        (someone_id, "resume"),
        (other_id, "dashboard"),
    ]
    for user_id, source in made:
        with ai_calls.called_by(user_id, source):
            await ai_calls.record(
                purpose="job-read", model="m", own_key=False, ok=True, duration_ms=5
            )

    page = (await admin.get(f"{ADMIN}/ai-calls", params={"user_id": str(someone_id)})).json()
    assert [row["source"] for row in page["items"]] == ["resume", "extension"]
    assert {row["user_email"] for row in page["items"]} == {email_of(someone)}

    only_extension = (
        await admin.get(
            f"{ADMIN}/ai-calls", params={"user_id": str(someone_id), "source": "extension"}
        )
    ).json()
    assert [row["source"] for row in only_extension["items"]] == ["extension"]

    summary = (await admin.get(f"{ADMIN}/ai-calls/summary")).json()
    assert summary["by_source"]["extension"] >= 1 and summary["by_source"]["resume"] >= 1
