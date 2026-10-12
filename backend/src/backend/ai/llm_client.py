"""Gemini client: the single place every model call goes through.

Two fallbacks, because two different things go wrong:

- Models: when a model is overloaded (5xx) or times out, that is true for every
  key, so we move to the next model in `llm_model` + `llm_fallback_models` and
  use the first one that answers.
- Keys: when a key is rejected, or out of quota on this model, we move to the
  next key: server key 1, server key 2, then the caller's own saved key (if
  they added one in Settings). A rejected key is not tried again; a key that
  is only out of quota is, because quota is counted per model.

Only once every model has failed do we raise, and the message points the user
at adding their own key.
"""

import asyncio
import logging
import time

from google import genai
from google.genai import errors
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from backend.core.config import get_settings
from backend.core.exceptions import AppError

logger = logging.getLogger(__name__)

# A model that just failed is skipped for a while, so one outage costs a single
# slow request instead of every request waiting out the timeout. This is only a
# per-process hint: losing it (restart, another instance) just means one retry.
_MODEL_COOLDOWN_SECONDS = 300.0
_cooling_until: dict[str, float] = {}


def _models_to_try() -> list[str]:
    """Healthy models first; ones cooling down are kept as a last resort."""
    now = time.monotonic()
    models = _candidate_models()
    healthy = [m for m in models if _cooling_until.get(m, 0.0) <= now]
    return healthy + [m for m in models if m not in healthy]


class LLMUnavailableError(AppError):
    status_code = 503
    detail = "AI service is temporarily unavailable. Add your own Gemini API key in Settings."


class InvalidLLMKeyError(AppError):
    status_code = 422
    detail = (
        "Google rejected this API key. Check that you copied the whole key "
        "and that the Gemini API is enabled for it."
    )


class LLMKeyQuotaError(AppError):
    status_code = 422
    detail = (
        "This key is valid, but Google says it has no quota left right now. "
        "Check its usage limits in Google AI Studio, then try again."
    )


class LLMKeyCheckUnavailableError(AppError):
    status_code = 503
    detail = "Could not reach Google to test this key, so nothing was saved. Please try again."


_KEY_REJECTED_CODES = {400, 401, 403}


async def verify_api_key(key: str) -> None:
    """Prove a key can actually generate by making the smallest possible model call.

    Listing models would be cheaper, but it passes for keys that cannot generate,
    which is the only thing a saved key is ever used for.
    """
    settings = get_settings()
    client = genai.Client(api_key=key)
    last_error: Exception | None = None
    for model in _candidate_models():
        try:
            await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents="ping",
                    config={"max_output_tokens": 1, "temperature": 0},
                ),
                timeout=settings.llm_key_check_timeout_seconds,
            )
            return
        except errors.ClientError as exc:
            if exc.code in _KEY_REJECTED_CODES:
                raise InvalidLLMKeyError() from exc
            if exc.code == 429:
                raise LLMKeyQuotaError() from exc
            logger.warning("Key check on %s failed (status %s): %s", model, exc.code, exc.message)
            last_error = exc
        except (errors.APIError, TimeoutError) as exc:
            # An outage on one model says nothing about the key; try the next model.
            logger.warning("Key check on %s could not complete: %s", model, type(exc).__name__)
            last_error = exc
    raise LLMKeyCheckUnavailableError() from last_error


def _candidate_models() -> list[str]:
    settings = get_settings()
    return list(dict.fromkeys([settings.llm_model, *settings.llm_fallback_models]))


def _candidate_keys(user_api_key: str | None) -> list[str]:
    settings = get_settings()
    return [k for k in (settings.llm_api_key_1, settings.llm_api_key_2, user_api_key) if k]


async def _call_once[T: BaseModel](
    key: str,
    model: str,
    prompt: str,
    response_schema: type[T] | type[list[T]],
    system_instruction: str | None,
) -> T | list[T]:
    settings = get_settings()
    config: genai.types.GenerateContentConfigDict = {
        "response_mime_type": "application/json",
        "response_schema": response_schema,
        "temperature": 0,
    }
    if system_instruction:
        config["system_instruction"] = system_instruction

    client = genai.Client(api_key=key)
    response = await asyncio.wait_for(
        client.aio.models.generate_content(model=model, contents=prompt, config=config),
        timeout=settings.llm_timeout_seconds,
    )
    if response.parsed is None:
        raise TimeoutError("Model returned no parseable output")
    return response.parsed  # type: ignore[return-value]


def _is_key_problem(exc: errors.ClientError) -> bool:
    """True when the key itself is rejected, so no model would accept it.

    Quota (429) is deliberately not here: Gemini counts quota per model, so a key
    that is out of quota on one model can still work on the next.
    """
    if exc.code in (401, 403):
        return True
    return exc.code == 400 and "api key" in (exc.message or "").lower()


async def generate_structured[T: BaseModel](
    prompt: str,
    response_schema: type[T] | type[list[T]],
    *,
    user_api_key: str | None = None,
    system_instruction: str | None = None,
) -> T | list[T]:
    keys = _candidate_keys(user_api_key)
    if not keys:
        raise LLMUnavailableError("No Gemini API key is configured")

    unusable_keys: set[str] = set()
    last_error: Exception | None = None

    for model in _models_to_try():
        for number, key in enumerate(keys, start=1):
            if key in unusable_keys:
                continue
            try:
                # One quick retry for a blip; a model that stays down is left behind.
                async for attempt in AsyncRetrying(
                    retry=retry_if_exception_type(errors.ServerError),
                    stop=stop_after_attempt(2),
                    wait=wait_exponential_jitter(initial=0.5, max=2),
                    reraise=True,
                ):
                    with attempt:
                        result = await _call_once(
                            key, model, prompt, response_schema, system_instruction
                        )
                if model != get_settings().llm_model:
                    logger.warning("Answered by fallback model %s", model)
                return result
            except errors.ClientError as exc:
                last_error = exc
                if _is_key_problem(exc):
                    logger.warning("Gemini key #%d unusable (status %s)", number, exc.code)
                    unusable_keys.add(key)
                    continue
                # Out of quota on this model (429) or no access to it (404):
                # another key might still work here, and this key on another model.
                logger.warning("%s refused key #%d (status %s)", model, number, exc.code)
            except (errors.APIError, TimeoutError) as exc:
                # Overloaded or hung: every key would hit the same wall, so change model.
                logger.warning("%s unavailable (%s), moving on", model, type(exc).__name__)
                _cooling_until[model] = time.monotonic() + _MODEL_COOLDOWN_SECONDS
                last_error = exc
                break

    raise LLMUnavailableError() from last_error
