from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = True

    # Postgres (Neon) + pgvector
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rolesetu"

    # Firebase Auth — service account JSON path, used to verify ID tokens
    firebase_service_account_path: str | None = None
    # Verifying ID tokens only needs the project id (Google's public keys do the rest).
    firebase_project_id: str | None = None

    # CORS — dashboard origin(s)
    cors_origins: list[str] = ["http://localhost:3000"]

    # Cloudflare R2 (S3-compatible)
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_public_url: str | None = None

    # Gemini — two server-side keys tried in order before falling back to a
    # user-supplied key (see ai/llm_client.py for the fallback chain).
    llm_api_key_1: str | None = None
    llm_api_key_2: str | None = None
    llm_model: str = "gemini-flash-latest"
    # Tried in order when the primary model is overloaded, timing out or unavailable.
    llm_fallback_models: list[str] = [
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-flash-lite-latest",
    ]
    llm_timeout_seconds: float = 30.0

    # How job checks are scored. "local" uses the skills dictionary and makes no
    # model call (instant, free). "llm" asks Gemini to read the job and judge it.
    match_engine: Literal["local", "llm"] = "local"
    # A local embedding model that finds skills a profile shows without naming.
    # Off for now: on the jobs measured it changed almost no verdicts while
    # costing about 220 MB of memory. Set SEMANTIC_MATCHING=true to turn it on.
    semantic_matching: bool = False

    # Context.dev: reads job pages our own fetch cannot (sites that block bots or
    # need JavaScript). Paid per call, so it is only tried after our fetch fails.
    # Keys are tried in order; with none set, the fallback is simply off.
    context_api_keys: list[str] = []
    context_timeout_seconds: float = 25.0
    # Paid reads a day the landing page's job preview may use, across all visitors.
    # Signed-in users have their own allowance, so this cannot starve them.
    preview_rendered_reads_per_day: int = 20

    # Gmail (read-only). Created in Google Cloud Console; without them the
    # "Connect Gmail" button reports that Gmail is not set up.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/inbox/gmail/callback"
    # Where the browser is sent back to after Google's consent screen.
    dashboard_url: str = "http://localhost:3000"
    # How far back the first sync of a newly connected inbox looks.
    inbox_lookback_days: int = 15

    # Resend: sends the email that confirms a place on the extension waiting
    # list. With no key set, nothing is sent and joining still works.
    resend_api_key: str | None = None
    # Must be an address on a domain verified in Resend. The default is Resend's
    # test sender, which only delivers to the Resend account's own address.
    email_from: str = "Rolesetu <onboarding@resend.dev>"
    # Where a reply goes (the email asks people to reply to be taken off the list).
    email_reply_to: str | None = None
    email_timeout_seconds: float = 10.0

    # Extra folder searched for fonts when a resume's own font lacks a letter.
    font_dir: str | None = None
    model_cache_dir: str = ".model_cache"
    llm_key_check_timeout_seconds: float = 10.0

    # Symmetric key (Fernet) used to encrypt user-supplied API keys at rest.
    encryption_key: str | None = None

    # Observability
    sentry_dsn: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
