"""Resolve a profile's line of work from AI output and role titles."""

from backend.ai.profile_understanding import ProfileUnderstanding
from backend.modules.matches.local import fields
from backend.modules.profiles.schemas import ProfileWrite

_KNOWN_KEYS = frozenset(field.key for field in fields.FIELDS)


def normalize_field_key(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    key = raw.strip().lower().replace(" ", "_")
    if key in ("general", "unknown"):
        return None
    if key in _KNOWN_KEYS:
        return key
    return None


def fields_from_profile(profile: ProfileWrite) -> list[str]:
    return fields.fields_of_person(
        [(item.title, item.start, item.end) for item in profile.experience],
        profile.headline,
        [f"{item.field or ''} {item.degree}" for item in profile.education],
    )


def resolve_field(
    profile: ProfileWrite, ai: ProfileUnderstanding | None = None
) -> tuple[str | None, str | None, str | None]:
    """Returns `(field_key, scope_summary, inferred_field_key)`.

    `field_key` is the best default for the profile. When AI and titles disagree,
    `inferred_field_key` holds the title-based guess so the UI can ask the user.
    """
    scope = (ai.scope_summary.strip() if ai and ai.scope_summary else "") or None
    ai_key = normalize_field_key(ai.field if ai else None)
    title_keys = fields_from_profile(profile)
    title_key = title_keys[0] if title_keys else None

    if ai_key and title_key and ai_key != title_key:
        return ai_key, scope, title_key
    if ai_key:
        return ai_key, scope, None
    if title_key:
        return title_key, scope, None
    return None, scope, None
