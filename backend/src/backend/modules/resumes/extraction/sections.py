"""Splits a resume into its sections by recognising heading lines."""

import re
from typing import Literal

from backend.modules.resumes.extraction.lines import Line

Section = Literal["header", "summary", "experience", "education", "skills", "projects", "other"]

_HEADINGS: dict[Section, tuple[str, ...]] = {
    "experience": (
        "experience", "work experience", "professional experience", "employment",
        "employment history", "work history", "career history", "internships", "internship",
        "internship experience", "experience and internships", "relevant experience",
        "industry experience", "professional background", "work", "career",
    ),
    "education": (
        "education", "academic background", "academics", "academic qualifications",
        "educational qualifications", "education and training", "academic details",
        "educational background", "qualifications",
    ),
    "skills": (
        "skills", "technical skills", "core skills", "key skills", "skills and tools",
        "technologies", "tech stack", "core competencies", "areas of expertise",
        "technical proficiencies", "tools and technologies", "skills and technologies",
        "technical expertise", "skill set", "skillset", "skills summary", "technical summary",
        "programming skills", "it skills", "expertise",
    ),
    "projects": (
        "projects", "personal projects", "academic projects", "key projects",
        "selected projects", "side projects", "project experience", "notable projects",
        "open source", "open source projects", "open source contributions",
    ),
    "summary": (
        "summary", "profile", "about", "about me", "objective", "professional summary",
        "career objective", "career summary", "personal summary", "overview", "introduction",
    ),
    "other": (
        "certifications", "certificates", "licenses and certifications", "achievements",
        "awards", "awards and honors", "honors", "honors and awards", "publications",
        "languages", "interests", "hobbies", "hobbies and interests", "references", "volunteer",
        "volunteering", "volunteer experience", "extracurricular", "extracurricular activities",
        "leadership", "positions of responsibility", "courses", "coursework",
        "relevant coursework", "activities", "contact", "contact details", "contact information",
        "links", "declaration", "personal details", "personal information", "trainings",
        "training", "accomplishments", "strengths", "additional information", "patents",
        "conferences", "memberships", "social", "profiles",
    ),
}  # fmt: skip

_LOOKUP: dict[str, Section] = {
    variant: section for section, variants in _HEADINGS.items() for variant in variants
}


def _normalise(text: str) -> str:
    cleaned = text.lower().replace("&", " and ")
    cleaned = re.sub(r"[^a-z ]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def heading_of(line: Line) -> Section | None:
    """The section a line introduces, or None if it is ordinary text.

    A heading is a short line that says only the section name. "Languages:
    Python, Go" is content, not a heading, because something follows the name.
    """
    text = line.flat
    if not text or len(text) > 45 or len(text.split()) > 5:
        return None
    if ":" in text.rstrip(":"):
        return None
    return _LOOKUP.get(_normalise(text))


def split_sections(lines: list[Line]) -> dict[Section, list[Line]]:
    sections: dict[Section, list[Line]] = {"header": []}
    current: Section = "header"
    for line in lines:
        heading = heading_of(line)
        if heading is not None:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections
