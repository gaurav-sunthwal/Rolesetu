"""The model call falls back across models (outages) and keys (rejections)."""

from typing import Any

import httpx
import pytest
from google import genai
from google.genai import errors
from pydantic import BaseModel

from backend.ai import llm_client
from backend.ai.llm_client import LLMUnavailableError, generate_structured
from backend.core.config import get_settings


class Answer(BaseModel):
    text: str


def _error(kind: type[errors.APIError], code: int, message: str = "nope") -> errors.APIError:
    response = httpx.Response(code, request=httpx.Request("POST", "https://example.test"))
    return kind(code, {"error": {"code": code, "message": message, "status": "X"}}, response)


class FakeGemini:
    """`outcomes[(key, model)]` is an exception to raise; anything missing answers."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, outcomes: dict[tuple[str, str], Exception]):
        self.calls: list[tuple[str, str]] = []
        fake = self

        class _Models:
            def __init__(self, key: str) -> None:
                self.key = key

            async def generate_content(self, *, model: str, **_: Any) -> object:
                fake.calls.append((self.key, model))
                outcome = outcomes.get((self.key, model))
                if outcome is not None:
                    raise outcome
                return type("Response", (), {"parsed": Answer(text=f"{self.key}/{model}")})()

        class _Client:
            def __init__(self, api_key: str) -> None:
                self.aio = type("Aio", (), {"models": _Models(api_key)})()

        monkeypatch.setattr(genai, "Client", _Client)
        settings = get_settings()
        monkeypatch.setattr(settings, "llm_api_key_1", "k1")
        monkeypatch.setattr(settings, "llm_api_key_2", "k2")
        monkeypatch.setattr(settings, "llm_model", "primary")
        monkeypatch.setattr(settings, "llm_fallback_models", ["backup", "last"])


@pytest.fixture(autouse=True)
def _no_backoff_and_no_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "wait_exponential_jitter", lambda **_: lambda *_: 0)
    monkeypatch.setattr(llm_client, "_cooling_until", {})


async def test_primary_model_is_used_when_it_works(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini = FakeGemini(monkeypatch, {})
    result = await generate_structured("hi", Answer)
    assert isinstance(result, Answer) and result.text == "k1/primary"
    assert gemini.calls == [("k1", "primary")]


async def test_overloaded_model_falls_back_to_the_next_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overloaded = _error(errors.ServerError, 503)
    gemini = FakeGemini(monkeypatch, {("k1", "primary"): overloaded, ("k2", "primary"): overloaded})
    result = await generate_structured("hi", Answer)

    assert isinstance(result, Answer) and result.text == "k1/backup"
    # One retry on the primary, then straight to the backup: key 2 is not
    # wasted on a model that is down for everyone.
    assert gemini.calls == [("k1", "primary"), ("k1", "primary"), ("k1", "backup")]


async def test_rejected_key_is_skipped_for_every_model(monkeypatch: pytest.MonkeyPatch) -> None:
    rejected = _error(errors.ClientError, 400, "API key not valid. Please pass a valid API key.")
    overloaded = _error(errors.ServerError, 503)
    gemini = FakeGemini(monkeypatch, {("k1", "primary"): rejected, ("k2", "primary"): overloaded})
    result = await generate_structured("hi", Answer)

    assert isinstance(result, Answer) and result.text == "k2/backup"
    assert ("k1", "backup") not in gemini.calls


async def test_model_a_key_cannot_use_tries_the_other_key(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeGemini(monkeypatch, {("k1", "primary"): _error(errors.ClientError, 404)})
    result = await generate_structured("hi", Answer)
    assert isinstance(result, Answer) and result.text == "k2/primary"


async def test_user_key_is_the_last_resort(monkeypatch: pytest.MonkeyPatch) -> None:
    quota = _error(errors.ClientError, 429)
    FakeGemini(monkeypatch, {("k1", "primary"): quota, ("k2", "primary"): quota})
    result = await generate_structured("hi", Answer, user_api_key="mine")
    assert isinstance(result, Answer) and result.text == "mine/primary"


async def test_raises_only_when_every_model_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    overloaded = _error(errors.ServerError, 503)
    gemini = FakeGemini(
        monkeypatch, {("k1", model): overloaded for model in ("primary", "backup", "last")}
    )
    with pytest.raises(LLMUnavailableError):
        await generate_structured("hi", Answer)
    assert {model for _, model in gemini.calls} == {"primary", "backup", "last"}


async def test_a_model_that_just_failed_is_skipped_next_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overloaded = _error(errors.ServerError, 503)
    gemini = FakeGemini(monkeypatch, {("k1", "primary"): overloaded})
    await generate_structured("hi", Answer)
    gemini.calls.clear()

    result = await generate_structured("hi", Answer)
    assert isinstance(result, Answer) and result.text == "k1/backup"
    assert gemini.calls == [("k1", "backup")]


async def test_cooling_models_are_still_tried_as_a_last_resort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overloaded = _error(errors.ServerError, 503)
    outcomes: dict[tuple[str, str], Exception] = {
        ("k1", model): overloaded for model in ("primary", "backup", "last")
    }
    FakeGemini(monkeypatch, outcomes)
    with pytest.raises(LLMUnavailableError):
        await generate_structured("hi", Answer)

    # Everything is cooling down, but the primary has recovered.
    del outcomes[("k1", "primary")]
    result = await generate_structured("hi", Answer)
    assert isinstance(result, Answer) and result.text == "k1/primary"


async def test_quota_on_one_model_does_not_write_the_key_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quota = _error(errors.ClientError, 429)
    FakeGemini(monkeypatch, {("k1", "primary"): quota, ("k2", "primary"): quota})
    result = await generate_structured("hi", Answer)
    assert isinstance(result, Answer) and result.text == "k1/backup"
