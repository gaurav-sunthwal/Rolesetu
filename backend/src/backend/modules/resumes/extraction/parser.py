"""Runs the whole local pipeline: PDF bytes in, `ParsedResume` out."""

from backend.modules.resumes.extraction.contact import parse_contact
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


def parse_pdf(pdf: bytes) -> ParsedResume:
    lines = extract_lines(pdf)
    if sum(len(line.flat) for line in lines) < MIN_TEXT_CHARACTERS:
        raise NoTextInPdfError
    return parse_lines(lines)
