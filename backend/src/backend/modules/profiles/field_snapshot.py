"""Onboarding snapshot: typical skills for the profile's field vs evidence."""

import contextlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.modules.ai_calls.service import called_by
from backend.modules.domain_catalogs import service as domain_catalogs_service
from backend.modules.llm_keys.service import get_decrypted_user_llm_key
from backend.modules.matches.local import fields
from backend.modules.matches.local.catalog import Skill, lookup
from backend.modules.matches.local.domain_catalogs import (
    HAND_AUTHORED_FIELDS,
    field_keys_for_profile,
)
from backend.modules.matches.local.jd import Requirement
from backend.modules.matches.local.judge import ProfileIndex
from backend.modules.matches.local.semantic import get_matcher
from backend.modules.matches.schemas import SkillResult
from backend.modules.profiles.schemas import FieldSnapshotRead, ProfileRead


async def build_field_snapshot(
    db: AsyncSession, *, user_id: uuid.UUID, profile: ProfileRead
) -> FieldSnapshotRead:
    field_key = profile.field_key
    user_api_key = await get_decrypted_user_llm_key(db, user_id=user_id)

    if field_key and field_key not in HAND_AUTHORED_FIELDS:
        with called_by(user_id, "dashboard"):
            await domain_catalogs_service.ensure_catalog(db, field_key, user_api_key=user_api_key)

    append_keys = field_keys_for_profile(profile)
    catalog_append = await domain_catalogs_service.catalog_append_for_fields(db, append_keys)
    with called_by(user_id, "dashboard"):
        core = await domain_catalogs_service.core_skills_for_field(
            db, field_key, user_api_key=user_api_key
        )

    field_label = None
    inferred_label = None
    if field_key:
        with contextlib.suppress(KeyError):
            field_label = fields.label(field_key)
    if profile.inferred_field_key:
        with contextlib.suppress(KeyError):
            inferred_label = fields.label(profile.inferred_field_key)

    if not field_key or not core:
        return FieldSnapshotRead(
            field_key=field_key,
            field_label=field_label,
            scope_summary=profile.scope_summary,
            inferred_field_key=profile.inferred_field_key,
            inferred_field_label=inferred_label,
            catalog_status="unavailable",
            skills=[],
        )

    matcher = get_matcher() if get_settings().semantic_matching else None
    index = ProfileIndex(profile, matcher, catalog_append=catalog_append)
    results: list[SkillResult] = []
    for name in core:
        skill = lookup(name, index.extra, catalog_append) or Skill(name=name, catalog=False)
        judgement = index.judge(Requirement(options=(skill,), required=True))
        results.append(
            SkillResult(
                name=judgement.name,
                required=judgement.required,
                verdict=judgement.verdict,
                evidence_label=judgement.evidence_label,
                evidence_text=judgement.evidence_text,
                reason=judgement.reason,
            )
        )

    return FieldSnapshotRead(
        field_key=field_key,
        field_label=field_label,
        scope_summary=profile.scope_summary,
        inferred_field_key=profile.inferred_field_key,
        inferred_field_label=inferred_label,
        catalog_status="ready",
        skills=results,
    )
