"""Runs the whole local pipeline: PDF bytes in, `ParsedResume` out."""

from dataclasses import dataclass

from backend.modules.resumes.extraction.contact import find_email, parse_contact
from backend.modules.resumes.extraction.education import parse_education
from backend.modules.resumes.extraction.experience import parse_experience
from backend.modules.resumes.extraction.lines import Line
from backend.modules.resumes.extraction.pdf_lines import extract_lines
from backend.modules.resumes.extraction.projects import parse_projects
from backend.modules.resumes.extraction.sections import split_sections
from backend.modules.resumes.extraction.skills import parse_skills
from backend.modules.resumes.parsed import ParsedResume

# Bump when the rules change, so stored results record what produced them.
PARSER_VERSION = "local.v2"
# Less text than this means the PDF is a scan or an image, not real text.
MIN_TEXT_CHARACTERS = 150


class NoTextInPdfError(Exception):
    """The PDF has no selectable text (it is a scan or a picture)."""


@dataclass(frozen=True)
class Identity:
    """Who the resume belongs to: enough to start an account, nothing more."""

    full_name: str | None
    email: str | None


def parse_lines(lines: list[Line]) -> ParsedResume:
    sections = split_sections(lines)
    contact = parse_contact(sections.get("header", []), lines)
    experience = parse_experience(sections.get("experience", []))
    resume = ParsedResume(
        **contact,
        skills=parse_skills(sections.get("skills", [])),
        experience=experience,
        projects=parse_projects(sections.get("projects", [])),
        education=parse_education(sections.get("education", [])),
    )
    if resume.headline is None and experience:
        resume.headline = experience[0].title
    return resume


def _text_lines(pdf: bytes) -> list[Line]:
    lines = extract_lines(pdf)
    if sum(len(line.flat) for line in lines) < MIN_TEXT_CHARACTERS:
        raise NoTextInPdfError
    return lines


def parse_pdf(pdf: bytes) -> ParsedResume:
    return parse_lines(_text_lines(pdf))


def read_identity(pdf: bytes) -> Identity:
    lines = _text_lines(pdf)
    header = split_sections(lines).get("header", [])
    return Identity(
        full_name=parse_contact(header, lines)["full_name"],
        email=find_email(header, lines),
    )
