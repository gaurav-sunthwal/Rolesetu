"""Which domain catalogs apply to a match or onboarding snapshot."""

from backend.modules.matches.local import fields
from backend.modules.profiles.schemas import ProfileRead

HAND_AUTHORED_FIELDS = frozenset({"software", "data"})
# Always merged into job checks so cross-field tools (SQL, Excel, etc.) stay found.
ALWAYS_INCLUDE_FIELDS = frozenset({"software", "data"})

CORE_SKILLS_HAND: dict[str, tuple[str, ...]] = {
    "software": (
        "Software development",
        "JavaScript",
        "Python",
        "Git",
        "REST APIs",
        "SQL",
        "Debugging",
        "Unit testing",
        "Code review",
        "Agile",
    ),
    "data": (
        "SQL",
        "Data analysis",
        "Python",
        "Excel",
        "Data modeling",
        "ETL",
        "Power BI",
        "Statistics",
        "Machine learning",
        "Data visualization",
    ),
}


def core_skills_for_hand_field(field_key: str) -> list[str]:
    return list(CORE_SKILLS_HAND.get(field_key, ()))


def field_keys_for_profile(profile: ProfileRead) -> set[str]:
    keys = set(ALWAYS_INCLUDE_FIELDS)
    if profile.field_key:
        keys.add(profile.field_key)
    for key in fields.fields_of_person(
        [(item.title, item.start, item.end) for item in profile.experience],
        profile.headline,
        [f"{item.field or ''} {item.degree}" for item in profile.education],
    ):
        keys.add(key)
    return keys


def field_keys_for_match(profile: ProfileRead, job_role: str | None) -> set[str]:
    """Catalogs this check may build. Only the person's own field.

    Whether the job is in that field is decided from the role title and the
    profile, in code. A mechanical posting checked by an HR profile does not
    add "mechanical" here, so it never spends a model call.
    """
    del job_role
    return field_keys_for_profile(profile)


def catalog_append_from_rows(rows: dict[str, str]) -> str:
    return "\n".join(text for text in rows.values() if text.strip())
