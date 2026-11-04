"""How long each request took, and how much of it was the database.

Every response carries a `Server-Timing` header (shown in the browser's
DevTools, Network > Timing) with the total time, the time spent waiting on the
database and the number of queries. A slow request is also logged, so the
same breakdown can be read from the server's logs.

The database is in another data centre from the API, so every query costs a
round trip; this is how to see where a slow request's time went.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# A request slower than this is logged with its breakdown.
SLOW_AFTER_MS = 800


@dataclass
class _Tally:
    queries: int = 0
    db_seconds: float = 0.0
    started: list[float] = field(default_factory=list)


_tally: ContextVar[_Tally | None] = ContextVar("request_timing", default=None)


def watch_queries(engine: AsyncEngine) -> None:
    """Counts the queries made on `engine` against the request that made them."""

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before(*_: Any) -> None:
        tally = _tally.get()
        if tally is not None:
            tally.started.append(time.perf_counter())

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after(*_: Any) -> None:
        tally = _tally.get()
        if tally is not None and tally.started:
            tally.db_seconds += time.perf_counter() - tally.started.pop()
            tally.queries += 1


def add_timing(app: FastAPI) -> None:
    @app.middleware("http")
    async def server_timing(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        tally = _Tally()
        token = _tally.set(tally)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            _tally.reset(token)
        total_ms = (time.perf_counter() - started) * 1000
        db_ms = tally.db_seconds * 1000
        response.headers["Server-Timing"] = (
            f'db;desc="{tally.queries} queries";dur={db_ms:.0f}, total;dur={total_ms:.0f}'
        )
        # Lets the dashboard and the extension's pages show these numbers too.
        response.headers["Timing-Allow-Origin"] = "*"
        if total_ms > SLOW_AFTER_MS:
            logger.info(
                "slow request %s %s: %.0f ms, %d queries taking %.0f ms",
                request.method,
                request.url.path,
                total_ms,
                tally.queries,
                db_ms,
            )
        return response
