from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
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
    # The same key file's contents, for hosts where an env var is easier than a
    # file (Railway). Used to delete a person's sign-in when their account is deleted.
    firebase_service_account_json: str | None = None
    # Verifying ID tokens only needs the project id (Google's public keys do the rest).
    firebase_project_id: str | None = None

    # Google accounts allowed into the admin panel (verified emails). Empty: nobody.
    admin_emails: list[str] = []
    # Told by email each time someone signs in for the first time. Empty: nobody.
    signup_alert_emails: list[str] = []

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
    # How long Context.dev may take over one try, and how many tries a page gets.
    # The same page can take ten seconds one time and stall the next, so two
    # short tries succeed more often than one long one. Together with our own
    # fetch this stays inside the minute the website waits for a job check.
    context_timeout_seconds: float = 15.0
    context_attempts: int = 2
    # Paid reads a day the landing page's job preview may use, across all visitors.
    # Signed-in users have their own allowance, so this cannot starve them.
    preview_rendered_reads_per_day: int = 20

    # Collect jobs from company careers sites once a day inside the API. Unset:
    # on in production only, so a laptop pointed at a shared database does not
    # collect as well. Set CAREER_JOBS_AUTO_COLLECT=true or false to override.
    career_jobs_auto_collect: bool | None = None

    @property
    def collects_career_jobs(self) -> bool:
        if self.career_jobs_auto_collect is not None:
            return self.career_jobs_auto_collect
        return self.environment == "production"

    # Gmail (read-only). Created in Google Cloud Console; without them the
    # "Connect Gmail" button reports that Gmail is not set up.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/inbox/gmail/callback"
    # Where the browser is sent back to after Google's consent screen.
    dashboard_url: str = "http://localhost:3000"
    # The extension's page on the Chrome Web Store, linked from emails.
    extension_store_url: str = (
        "https://chromewebstore.google.com/detail/bbpdnhlpapbkiadfdnkhacamojlkfbjl"
    )
    # How far back the first sync of a newly connected inbox looks.
    inbox_lookback_days: int = 15

    # Email (see core/email.py). Gmail is used when its refresh token is set,
    # else Resend when its key is set; with neither, nothing is sent.
    # Gmail sends from the account that signed in to make this token (with the
    # Google client above); get one with `python -m backend.scripts.gmail_sender_token`.
    gmail_sender_refresh_token: str | None = None
    resend_api_key: str | None = None
    # With Gmail: "Rolesetu <that-account@gmail.com>". With Resend: an address on
    # a domain verified in Resend (the default only reaches the Resend account).
    email_from: str = "Rolesetu <onboarding@resend.dev>"
    # Where a reply goes (the email asks people to reply to be taken off the list).
    email_reply_to: str | None = None
    email_timeout_seconds: float = 10.0
    # How long after someone first signs in they get the founder's one-time
    # note (modules/feedback).
    feedback_email_delay_hours: float = 3.0

    # Social posting from the admin panel (modules/social). Each platform's
    # "Connect" button stays disabled until its app id and secret are set.
    # Where the admin panel lives: the browser returns there after a platform's consent screen.
    admin_url: str = "http://localhost:3003"
    # This API's own public address. Instagram and Facebook download post images from it.
    public_api_url: str = "http://localhost:8000"
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    linkedin_redirect_uri: str = "http://localhost:8000/api/v1/admin/social/linkedin/callback"
    # LinkedIn's REST API is versioned by month (YYYYMM); each version works for about a year.
    linkedin_api_version: str = "202608"
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    meta_redirect_uri: str = "http://localhost:8000/api/v1/admin/social/meta/callback"
    meta_graph_version: str = "v23.0"
    social_timeout_seconds: float = 20.0
    # Publish scheduled posts from inside the API. Unset: on in production only,
    # so a laptop pointed at a shared database does not publish as well.
    social_auto_publish: bool | None = None

    @property
    def publishes_social_posts(self) -> bool:
        if self.social_auto_publish is not None:
            return self.social_auto_publish
        return self.environment == "production"

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

    @model_validator(mode="after")
    def production_stays_quiet(self) -> Self:
        # A production process must not echo SQL or leave the debug flag on,
        # even when DEBUG was left unset.
        if self.environment == "production":
            self.debug = False
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
