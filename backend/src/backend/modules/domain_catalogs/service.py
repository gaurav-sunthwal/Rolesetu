"""Generate and cache domain skill catalogs (once per field)."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.llm_client import generate_structured
from backend.ai.prompts import load_prompt
from backend.modules.domain_catalogs import repository
from backend.modules.domain_catalogs.models import DomainSkillCatalog
from backend.modules.matches.local import fields
from backend.modules.matches.local.domain_catalogs import (
    HAND_AUTHORED_FIELDS,
    core_skills_for_hand_field,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = 1
_FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "domain_catalogs"


class GeneratedCatalog(BaseModel):
    catalog_lines: list[str] = Field(min_length=10, max_length=40)
    core_skill_names: list[str] = Field(min_length=8, max_length=20)


def _format_catalog(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip())


def _fixture_path(field_key: str) -> Path:
    return _FIXTURES / f"{field_key}.v{repository.CATALOG_VERSION}.txt"


def load_fixture(field_key: str) -> tuple[str, list[str]] | None:
    path = _fixture_path(field_key)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    core: list[str] = []
    catalog_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# core:"):
            core = [
                part.strip() for part in stripped.removeprefix("# core:").split(",") if part.strip()
            ]
            continue
        if stripped and not stripped.startswith("#"):
            catalog_lines.append(stripped)
    if not catalog_lines or not core:
        return None
    return _format_catalog(catalog_lines), core


async def generate_catalog(
    field_key: str, *, user_api_key: str | None = None
) -> GeneratedCatalog | None:
    try:
        field_label = fields.label(field_key)
    except KeyError:
        return None
    system = load_prompt("generate_domain_catalog", PROMPT_VERSION).format(
        field_key=field_key, field_label=field_label
    )
    try:
        result = await generate_structured(
            f"Produce the skill dictionary for {field_label}.",
            GeneratedCatalog,
            purpose="generate-domain-catalog",
            user_api_key=user_api_key,
            system_instruction=system,
            timeout_seconds=25.0,
        )
        assert isinstance(result, GeneratedCatalog)
        return result
    except Exception as exc:
        logger.warning("Domain catalog generation failed for %s: %s", field_key, exc)
        return None


async def ensure_catalog(
    db: AsyncSession,
    field_key: str,
    *,
    user_api_key: str | None = None,
) -> DomainSkillCatalog | None:
    if field_key in HAND_AUTHORED_FIELDS or not field_key:
        return None
    existing = await repository.get(db, field_key)
    if existing is not None:
        return existing

    fixture = load_fixture(field_key)
    if fixture is not None:
        catalog_text, core = fixture
        return await repository.upsert(
            db,
            field_key=field_key,
            source="fixture",
            catalog_text=catalog_text,
            core_skill_names=core,
        )

    generated = await generate_catalog(field_key, user_api_key=user_api_key)
    if generated is None:
        return None
    return await repository.upsert(
        db,
        field_key=field_key,
        source="generated",
        catalog_text=_format_catalog(generated.catalog_lines),
        core_skill_names=generated.core_skill_names[:20],
    )


async def catalog_append_for_fields(db: AsyncSession, field_keys: set[str]) -> str:
    append_keys = {key for key in field_keys if key and key not in HAND_AUTHORED_FIELDS}
    rows = await repository.list_for_fields(db, append_keys)
    return "\n".join(row.catalog_text for row in rows if row.catalog_text.strip())


async def core_skills_for_field(
    db: AsyncSession, field_key: str | None, *, user_api_key: str | None = None
) -> list[str]:
    if not field_key:
        return []
    if field_key in HAND_AUTHORED_FIELDS:
        return core_skills_for_hand_field(field_key)
    row = await repository.get(db, field_key)
    if row is None:
        row = await ensure_catalog(db, field_key, user_api_key=user_api_key)
    if row is None:
        return []
    return list(row.core_skill_names)
