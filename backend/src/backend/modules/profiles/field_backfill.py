"""Fill field and scope on profiles created before domain routing existed.

New uploads already store these. Existing accounts keep working from titles
alone when the resume file or the model is unavailable. A field the user
already confirmed is left as it is.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.profile_understanding import understand_profile
from backend.core import storage
from backend.modules.domain_catalogs import service as domain_catalogs
from backend.modules.llm_keys.service import get_decrypted_user_llm_key
from backend.modules.matches.local.domain_catalogs import HAND_AUTHORED_FIELDS
from backend.modules.profiles.field_detection import resolve_field
from backend.modules.profiles.models import Profile
from backend.modules.profiles.schemas import ProfileWrite
from backend.modules.profiles.service import _DOCUMENT_FIELDS, _SCALAR_FIELDS
from backend.modules.resumes.extraction.pdf_lines import extract_lines
from backend.modules.resumes.repository import latest as latest_resume

logger = logging.getLogger(__name__)


def _write_of(profile: Profile) -> ProfileWrite:
    return ProfileWrite.model_validate(
        {field: getattr(profile, field) for field in (*_SCALAR_FIELDS, *_DOCUMENT_FIELDS)}
    )


async def _resume_understanding(db: AsyncSession, user_id: uuid.UUID):
    resume = await latest_resume(db, user_id)
    if resume is None or resume.status != "parsed":
        return None
    try:
        data = await storage.get_file(resume.storage_key)
        lines = extract_lines(data)
    except Exception:
        logger.info("Could not reread the stored resume for %s", user_id)
        return None
    text = "\n".join(line.text for line in lines)
    user_api_key = await get_decrypted_user_llm_key(db, user_id=user_id)
    return await understand_profile(text, user_api_key=user_api_key)


async def backfill_domain_fields(db: AsyncSession) -> list[str]:
    """Sets a missing field on every profile and caches a catalog per field.

    Returns one short line per profile, for the one-off run.
    """
    profiles = list((await db.scalars(select(Profile))).all())
    notes: list[str] = []
    needed: set[str] = set()

    for profile in profiles:
        if profile.field_key and profile.field_key not in HAND_AUTHORED_FIELDS:
            needed.add(profile.field_key)
        if profile.field_key:
            notes.append(f"kept {profile.user_id} as {profile.field_key}")
            continue

        write = _write_of(profile)
        if not write.headline and not write.experience and not write.education and not write.skills:
            notes.append(f"skipped {profile.user_id}: empty profile")
            continue

        ai = await _resume_understanding(db, profile.user_id)
        field_key, scope, inferred = resolve_field(write, ai)
        if not field_key and not scope:
            notes.append(f"skipped {profile.user_id}: no field in the profile")
            continue

        profile.field_key = field_key
        profile.scope_summary = scope
        profile.inferred_field_key = inferred
        profile.version += 1
        if field_key and field_key not in HAND_AUTHORED_FIELDS:
            needed.add(field_key)
        if inferred and inferred not in HAND_AUTHORED_FIELDS:
            needed.add(inferred)
        notes.append(
            f"set {profile.user_id} to {field_key or 'unset'}"
            + (f" (titles say {inferred})" if inferred else "")
        )

    for field_key in sorted(needed):
        row = await domain_catalogs.ensure_catalog(db, field_key)
        notes.append(f"catalog {field_key}: {row.source if row else 'not available'}")
    await db.flush()
    return notes
