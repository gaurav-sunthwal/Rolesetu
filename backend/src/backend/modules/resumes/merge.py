"""Combines a parsed resume with an existing profile. Pure functions, no I/O."""

from typing import Literal

from backend.modules.profiles.schemas import (
    EducationItem,
    ExperienceItem,
    Links,
    ProfileWrite,
    ProjectItem,
    SkillItem,
)
from backend.modules.resumes.normalize import (
    MAX_EDUCATION,
    MAX_EXPERIENCE,
    MAX_PROJECTS,
    MAX_SKILLS,
    sort_experience,
)

ApplyMode = Literal["merge", "replace"]


def _merge_skills(current: list[SkillItem], incoming: list[SkillItem]) -> list[SkillItem]:
    merged = [skill.model_copy() for skill in current]
    by_name = {skill.name.lower(): skill for skill in merged}
    for skill in incoming:
        existing = by_name.get(skill.name.lower())
        if existing is None:
            merged.append(skill)
            by_name[skill.name.lower()] = skill
        elif existing.level is None and skill.level is not None:
            existing.level = skill.level
    return merged[:MAX_SKILLS]


def _merge_experience(
    current: list[ExperienceItem], incoming: list[ExperienceItem]
) -> list[ExperienceItem]:
    merged = [role.model_copy() for role in current]
    by_key = {(role.title.lower(), role.company.lower()): role for role in merged}
    for role in incoming:
        existing = by_key.get((role.title.lower(), role.company.lower()))
        if existing is None:
            merged.append(role)
            continue
        # Same role already on the profile: only fill what is blank there.
        existing.description = existing.description or role.description
        existing.location = existing.location or role.location
        if existing.start is None:
            existing.start, existing.end = role.start, role.end
    return sort_experience(merged)[:MAX_EXPERIENCE]


def _merge_projects(current: list[ProjectItem], incoming: list[ProjectItem]) -> list[ProjectItem]:
    merged = [project.model_copy() for project in current]
    by_name = {project.name.lower(): project for project in merged}
    for project in incoming:
        existing = by_name.get(project.name.lower())
        if existing is None:
            merged.append(project)
            continue
        existing.description = existing.description or project.description
        existing.url = existing.url or project.url
        existing.tech = existing.tech or project.tech
    return merged[:MAX_PROJECTS]


def _merge_education(
    current: list[EducationItem], incoming: list[EducationItem]
) -> list[EducationItem]:
    merged = [entry.model_copy() for entry in current]
    by_key = {(entry.school.lower(), entry.degree.lower()): entry for entry in merged}
    for entry in incoming:
        existing = by_key.get((entry.school.lower(), entry.degree.lower()))
        if existing is None:
            merged.append(entry)
            continue
        existing.field = existing.field or entry.field
        existing.start_year = existing.start_year or entry.start_year
        existing.end_year = existing.end_year or entry.end_year
    merged.sort(key=lambda entry: -(entry.end_year or entry.start_year or 0))
    return merged[:MAX_EDUCATION]


def apply_resume(current: ProfileWrite, parsed: ProfileWrite, mode: ApplyMode) -> ProfileWrite:
    """`replace` takes the resume as the whole profile. `merge` keeps everything
    already there, fills blanks, and adds what is new; it never overwrites.
    """
    if mode == "replace":
        return parsed.model_copy(deep=True)

    return ProfileWrite(
        full_name=current.full_name or parsed.full_name,
        headline=current.headline or parsed.headline,
        location=current.location or parsed.location,
        phone=current.phone or parsed.phone,
        links=Links(
            linkedin=current.links.linkedin or parsed.links.linkedin,
            github=current.links.github or parsed.links.github,
            portfolio=current.links.portfolio or parsed.links.portfolio,
        ),
        skills=_merge_skills(current.skills, parsed.skills),
        experience=_merge_experience(current.experience, parsed.experience),
        projects=_merge_projects(current.projects, parsed.projects),
        education=_merge_education(current.education, parsed.education),
    )
