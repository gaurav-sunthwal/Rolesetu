"""Turns raw model output into a valid profile. Pure functions, no I/O.

The model is asked to copy the resume faithfully, but nothing it returns is
trusted: every field is cleaned, length-limited and validated here, entries
missing their essentials are dropped, duplicates are removed, and lists are put
in a consistent order.
"""

import re
import uuid
from urllib.parse import urlparse

from backend.modules.profiles.schemas import (
    EducationItem,
    ExperienceItem,
    Links,
    ProfileWrite,
    ProjectItem,
    SkillItem,
)
from backend.modules.resumes.parsed import ParsedResume

MAX_SKILLS = 100
MAX_EXPERIENCE = 30
MAX_PROJECTS = 30
MAX_EDUCATION = 10
MAX_TECH = 25

_EMPTY_WORDS = {"", "n/a", "na", "none", "null", "nil", "-", "--", "not specified", "unknown"}
_YEAR_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_YEAR_ONLY = re.compile(r"^(\d{4})$")
_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.IGNORECASE)
_MIN_YEAR, _MAX_YEAR = 1950, 2100


def _text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[ \t ]+", " ", value).strip()
    if cleaned.lower() in _EMPTY_WORDS:
        return None
    return cleaned[:limit].rstrip()


def _multiline(value: str | None, limit: int) -> str:
    if not value:
        return ""
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in value.splitlines()]
    lines = [re.sub(r"^[•●▪‣⁃*\-–]\s+", "", line) for line in lines]
    return "\n".join(line for line in lines if line)[:limit].rstrip()


def _url(value: str | None) -> str | None:
    cleaned = _text(value, 300)
    if cleaned is None or " " in cleaned:
        return None
    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        cleaned = f"https://{cleaned}"
    host = urlparse(cleaned).netloc
    return cleaned if _DOMAIN.match(host.split(":")[0]) else None


def _year_month(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if _YEAR_MONTH.match(cleaned):
        year = int(cleaned[:4])
    elif _YEAR_ONLY.match(cleaned):
        year, cleaned = int(cleaned), f"{cleaned}-01"
    else:
        return None
    return cleaned if _MIN_YEAR <= year <= _MAX_YEAR else None


def _year(value: int | None) -> int | None:
    return value if value is not None and _MIN_YEAR <= value <= _MAX_YEAR else None


def _new_id() -> str:
    return str(uuid.uuid4())


def _skills(parsed: ParsedResume) -> list[SkillItem]:
    seen: set[str] = set()
    skills: list[SkillItem] = []
    for item in parsed.skills:
        name = _text(item.name, 60)
        if name is None or name.lower() in seen:
            continue
        seen.add(name.lower())
        skills.append(SkillItem(id=_new_id(), name=name, level=item.level))
    return skills[:MAX_SKILLS]


def _experience(parsed: ParsedResume) -> list[ExperienceItem]:
    roles: list[ExperienceItem] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in parsed.experience:
        title = _text(item.title, 160)
        company = _text(item.company, 160)
        # A role needs at least a title or an employer to mean anything.
        if title is None and company is None:
            continue
        start = _year_month(item.start)
        end = None if item.is_current else _year_month(item.end)
        if start and end and end < start:
            end = None
        key = ((title or "").lower(), (company or "").lower(), start)
        if key in seen:
            continue
        seen.add(key)
        roles.append(
            ExperienceItem(
                id=_new_id(),
                title=title or "Role not stated",
                company=company or "Company not stated",
                location=_text(item.location, 160),
                start=start,
                end=end,
                description=_multiline(item.description, 4000),
            )
        )
    return sort_experience(roles)[:MAX_EXPERIENCE]


def sort_experience(roles: list[ExperienceItem]) -> list[ExperienceItem]:
    """Current roles first, then most recent; undated roles last."""
    dated = sorted(
        (role for role in roles if role.start is not None),
        key=lambda role: (
            0 if role.end is None else 1,
            _descending(role.end or "9999-12"),
            _descending(role.start or ""),
        ),
    )
    return dated + [role for role in roles if role.start is None]


def _descending(year_month: str) -> int:
    digits = year_month.replace("-", "")
    return -int(digits) if digits.isdigit() else 0


def _projects(parsed: ParsedResume) -> list[ProjectItem]:
    projects: list[ProjectItem] = []
    seen: set[str] = set()
    for item in parsed.projects:
        name = _text(item.name, 160)
        if name is None or name.lower() in seen:
            continue
        seen.add(name.lower())
        tech: list[str] = []
        for entry in item.tech:
            cleaned = _text(entry, 60)
            if cleaned and cleaned.lower() not in {t.lower() for t in tech}:
                tech.append(cleaned)
        projects.append(
            ProjectItem(
                id=_new_id(),
                name=name,
                tech=tech[:MAX_TECH],
                description=_multiline(item.description, 4000),
                url=_url(item.url),
            )
        )
    return projects[:MAX_PROJECTS]


def _education(parsed: ParsedResume) -> list[EducationItem]:
    entries: list[EducationItem] = []
    seen: set[tuple[str, str]] = set()
    for item in parsed.education:
        school = _text(item.school, 160)
        degree = _text(item.degree, 160)
        if school is None:
            continue
        key = (school.lower(), (degree or "").lower())
        if key in seen:
            continue
        seen.add(key)
        start_year, end_year = _year(item.start_year), _year(item.end_year)
        if start_year and end_year and end_year < start_year:
            end_year = None
        entries.append(
            EducationItem(
                id=_new_id(),
                school=school,
                degree=degree or "Degree not stated",
                field=_text(item.field, 160),
                start_year=start_year,
                end_year=end_year,
            )
        )
    entries.sort(key=lambda e: -(e.end_year or e.start_year or 0))
    return entries[:MAX_EDUCATION]


def to_profile(parsed: ParsedResume) -> ProfileWrite:
    return ProfileWrite(
        full_name=_text(parsed.full_name, 160),
        headline=_text(parsed.headline, 160),
        location=_text(parsed.location, 160),
        phone=_text(parsed.phone, 40),
        links=Links(
            linkedin=_url(parsed.linkedin),
            github=_url(parsed.github),
            portfolio=_url(parsed.portfolio),
        ),
        skills=_skills(parsed),
        experience=_experience(parsed),
        projects=_projects(parsed),
        education=_education(parsed),
    )


def has_content(profile: ProfileWrite) -> bool:
    return bool(profile.skills or profile.experience or profile.projects or profile.education)
