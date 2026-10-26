import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import api_router
from backend.core.config import get_settings
from backend.core.exceptions import register_exception_handlers
from backend.db.session import get_engine
from backend.modules.career_jobs import schedule as career_jobs_schedule
from backend.modules.feedback import service as feedback
from backend.modules.matches.local import semantic
from backend.modules.social import publisher as social_publisher


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # Load the embedding model in the background, so startup is not held up and
    # the first job check does not pay for it.
    warm = asyncio.create_task(asyncio.to_thread(semantic.warm_up))
    collector = (
        asyncio.create_task(career_jobs_schedule.keep_collecting())
        if get_settings().collects_career_jobs
        else None
    )
    feedback_emails = asyncio.create_task(feedback.run_forever())
    social_posts = (
        asyncio.create_task(social_publisher.run_forever())
        if get_settings().publishes_social_posts
        else None
    )
    yield
    if social_posts is not None:
        social_posts.cancel()
    warm.cancel()
    if collector is not None:
        collector.cancel()
    feedback_emails.cancel()
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Rolesetu API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        if not settings.semantic_matching:
            matcher = "off"
        else:
            matcher = "ready" if semantic.get_matcher() is not None else "loading"
        return {"status": "ok", "semantic_matcher": matcher}

    return app


app = create_app()
