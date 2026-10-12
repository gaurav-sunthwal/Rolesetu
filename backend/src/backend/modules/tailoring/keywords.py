"""Compares a job's wording with the words on a resume, without a model:
which of the job's skills the resume names, which it names differently, and
whether the line under the candidate's name can carry the job's title.
"""

import re
from dataclasses import dataclass
from typing import Literal

from backend.modules.matches.local.catalog import find_skills
from backend.modules.tailoring.pdf.section import Line

# Words that make a line a job title rather than contact details.
_ROLE = re.compile(
    r"\b(developer|engineer|programmer|architect|designer|analyst|scientist|manager|"
    r"consultant|specialist|administrator|tester|intern|lead|officer|executive|"
    r"associate|sde|swe|devops|researcher|writer|marketer|recruiter)\b",
    re.IGNORECASE,
)
_CONTACT = re.compile(r"@|https?:|www\.|\.com\b|linkedin|github|\d{5,}", re.IGNORECASE)
# Rank a headline must not gain: the job may ask for it, the resume has to have earned it.
_SENIORITY = re.compile(
    r"\b(senior|sr|lead|principal|staff|head|chief|director|vp|manager|junior|jr|"
    r"associate|intern|trainee|entry[- ]level)\b\.?\s*",
    re.IGNORECASE,
)
# Kinds of work. A headline is only reworded within the same kind.
_FAMILIES = (
    r"developer|engineer|programmer|sde|swe|architect|devops",
    r"designer",
    r"analyst",
    r"scientist|researcher",
    r"manager|owner",
    r"tester|qa\b|quality",
    r"writer|marketer|recruiter|consultant|specialist",
)
_PARTS = re.compile(r"\s+[|·•–—-]\s+|\s{2,}\|\s{2,}")
_HEADLINE_SEARCH_LINES = 8
_MAX_TITLE = 60

SkillStatus = Literal["present", "different_spelling", "missing"]


@dataclass(frozen=True)
class SkillCheck:
    name: str
    status: SkillStatus
    # How the resume writes it, when that differs from the job's wording.
    written_as: str | None = None


@dataclass(frozen=True)
class Headline:
    """The line under the name, and the part of it that names the role."""

    line: Line
    role: str


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _has_word(text: str, phrase: str) -> bool:
    # "JS" must not be found inside "Next.js", so a dot before it also rules it out.
    pattern = rf"(?<![\w+#.]){re.escape(phrase)}(?![\w+#])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def check_skill(name: str, resume_text: str) -> SkillCheck:
    """Whether the resume names this skill, in the job's own wording or another."""
    if _has_word(resume_text, name):
        return SkillCheck(name, "present")
    wanted = {mention.skill.name for mention in find_skills(name)}
    for mention in find_skills(resume_text):
        if mention.skill.name in wanted:
            return SkillCheck(name, "different_spelling", resume_text[mention.start : mention.end])
    return SkillCheck(name, "missing")


def find_headline(lines: list[Line]) -> Headline | None:
    """The role line near the top of the first page, such as "React Native Developer"."""
    if not lines:
        return None
    for line in lines[1:_HEADLINE_SEARCH_LINES]:
        text = line.text
        if len(text) > 90 or _CONTACT.search(text) or not _ROLE.search(text):
            continue
        # "React Native Developer | Android & iOS": only the part naming the role.
        raw = "".join(span.text for span in line.spans)
        role = next((part for part in _PARTS.split(raw) if _ROLE.search(part)), None)
        if role and role.strip():
            return Headline(line=line, role=role.strip())
    return None


# What job sites wrap around a title: "Walk-in || ...", "Hiring for ...", "... jobs in Pune".
_TITLE_LEAD_IN = re.compile(
    r"^(?:walk[- ]?in(?: drive| interview)?|urgent(?:ly)?(?: hiring| requirement| opening)?|"
    r"(?:we are |now )?hiring(?: for)?|(?:job )?opening(?: for)?|vacancy(?: for)?|"
    r"immediate (?:joiner|opening)s?)\s*(?:for\b|[:|!-]|–)*\s*",
    re.IGNORECASE,
)
_TITLE_TAIL = re.compile(r"\s+(?:jobs?|vacanc(?:y|ies)|openings?)(?:\s+in\b.*)?$", re.IGNORECASE)


def clean_title(title: str) -> str:
    """A job title without what does not belong in a headline: "(Remote)", a
    city, a job code, or a job site's own wording around it.
    """
    text = re.sub(r"\s*[\[(].*?[\])]", "", title)
    text = _TITLE_TAIL.sub("", _TITLE_LEAD_IN.sub("", text.strip()))
    text = re.split(r"\s+[-–—|@,/]\s+|\s+at\s+", text)[0]
    return _flat(text)[:_MAX_TITLE]


def _family(text: str) -> int | None:
    return next(
        (i for i, words in enumerate(_FAMILIES) if re.search(rf"\b(?:{words})", text, re.I)), None
    )


def suggest_headline(current: str, job_title: str) -> str | None:
    """The job's title, written the way the current headline is, or None when
    the two are different kinds of work or already say the same thing.
    """
    wanted = clean_title(job_title)
    kept_rank = {match.group(1).lower() for match in _SENIORITY.finditer(current)}

    def earned(match: re.Match[str]) -> str:
        return match.group(0) if match.group(1).lower() in kept_rank else ""

    # Rank words stay only if the resume already claims them.
    wanted = _flat(_SENIORITY.sub(earned, wanted))
    if len(wanted) < 3 or _family(wanted) is None or _family(wanted) != _family(current):
        return None
    if current.isupper():
        wanted = wanted.upper()
    return None if _flat(wanted).lower() == _flat(current).lower() else wanted


def is_a_title(job_title: str) -> bool:
    """False for text that was taken for a title but is not one, such as a
    page heading ("Full job description").
    """
    return _ROLE.search(clean_title(job_title)) is not None


def title_present(job_title: str, resume_text: str) -> bool:
    return _has_word(_flat(resume_text), clean_title(job_title))


def find_spelling(raw_line: str, written_as: str, wanted: str) -> tuple[int, int] | None:
    """Where in a line the resume's spelling of a skill sits, as (start, end).
    Found through the skills dictionary, so "React" is never matched inside
    "React Native".
    """
    names = {mention.skill.name for mention in find_skills(wanted)}
    for mention in find_skills(raw_line):
        if mention.skill.name in names and (
            raw_line[mention.start : mention.end].lower() == written_as.lower()
        ):
            return (mention.start, mention.end)
    return None
