"""Counts every model call, for the admin panel's AI calls page.

The code that calls the model (`ai/llm_client.py`) only knows what it was
asked to do. Who asked, and from where, is set around the work by the code
that does know it, with `called_by`, and read here when the call is recorded.

Recording must never make things worse: it runs in its own database session,
swallows its own failures, and forgets calls after 90 days.
"""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from backend.db.session import get_sessionmaker
from backend.modules.ai_calls import repository
from backend.modules.ai_calls.models import AiCall

logger = logging.getLogger(__name__)

KEEP_FOR = timedelta(days=90)

Source = Literal["extension", "dashboard", "resume", "other"]


@dataclass(frozen=True)
class Caller:
    user_id: uuid.UUID
    source: Source


_caller: ContextVar[Caller | None] = ContextVar("ai_caller", default=None)


@contextmanager
def called_by(user_id: uuid.UUID, source: Source) -> Iterator[None]:
    """Every model call made inside this block is counted for this user and source."""
    token = _caller.set(Caller(user_id=user_id, source=source))
    try:
        yield
    finally:
        _caller.reset(token)


def current_caller() -> Caller | None:
    return _caller.get()


async def record(
    *,
    purpose: str,
    model: str | None,
    own_key: bool,
    ok: bool,
    duration_ms: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> None:
    """Writes one call. Never raises."""
    caller = current_caller()
    try:
        async with get_sessionmaker()() as db:
            db.add(
                AiCall(
                    user_id=caller.user_id if caller else None,
                    source=caller.source if caller else "other",
                    purpose=purpose,
                    model=model,
                    own_key=own_key,
                    ok=ok,
                    error=error,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms,
                )
            )
            await repository.delete_older_than(db, datetime.now(UTC) - KEEP_FOR)
            await db.commit()
    except Exception:
        logger.exception("Could not record an AI call")
