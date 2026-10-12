"""Education: school, degree, field of study and years."""

import re
from dataclasses import dataclass, field

from backend.modules.resumes.extraction import dates
from backend.modules.resumes.extraction.keywords import find_degree, has_school_word, is_place
from backend.modules.resumes.extraction.lines import Line, strip_bullet
from backend.modules.resumes.parsed import ParsedEducation

_STRONG_SPLIT = re.compile(r"\t|\s+[|•·—–]\s+|\s+-\s+")
_GRADE = re.compile(
    r"cgpa|gpa|sgpa|percent|percentage|%|grade|score|marks|aggregate|distinction|class\s+rank|"
    r"\d\s*/\s*\d|first\s+class|honou?rs|cbse|icse|igcse|board|hsc|ssc|isc",
    re.IGNORECASE,
)
_FIELD_LEAD = re.compile(
    r"^[\s,:\-\u2013(]*(?:(?:in|of|with\s+(?:a\s+)?(?:major|specialization)\s+in)\b)?\s*",
    re.IGNORECASE,
)


@dataclass
class _Entry:
    lines: list[str] = field(default_factory=list)
    has_school: bool = False
    has_degree: bool = False


def _split_entries(lines: list[Line]) -> list[_Entry]:
    entries: list[_Entry] = []
    current: _Entry | None = None
    for line in lines:
        text = strip_bullet(line.text)
        school, degree = has_school_word(text), find_degree(text) is not None
        new = (
            current is None
            or (school and current.has_school)
            or (degree and current.has_degree)
            or ((line.bold or line.lead_bold) and current.has_school and current.has_degree)
        )
        if new:
            if not (school or degree) and current is None:
                continue
            current = _Entry()
            entries.append(current)
        assert current is not None
        current.lines.append(text)
        current.has_school = current.has_school or school
        current.has_degree = current.has_degree or degree
    return entries


def _clean_field(text: str) -> str | None:
    text = _FIELD_LEAD.sub("", text, count=1)
    # Stop at the first thing that is clearly not part of the subject.
    text = re.split(r"[,;(|\t]|\s+[—–-]\s+|\s+(?:from|at)\s+", text, maxsplit=1)[0]
    text = text.strip(" .:-")
    if not text or _GRADE.search(text) or has_school_word(text) or is_place(text):
        return None
    if any(char.isdigit() for char in text) or len(text.split()) > 7:
        return None
    return text


def _read(entry: _Entry) -> ParsedEducation:
    education = ParsedEducation()
    text = " \t ".join(entry.lines)
    found = dates.find_range(text) or dates.find_single(text)
    if found is not None:
        education.start_year, education.end_year = found.start_year, found.end_year

    for raw_line in entry.lines:
        line_dates = dates.find_range(raw_line) or dates.find_single(raw_line)
        line = dates.remove(raw_line, line_dates) if line_dates else raw_line
        for piece in _STRONG_SPLIT.split(line):
            piece = piece.strip(" ,;:")
            if not piece:
                continue
            degree = find_degree(piece)
            if degree is not None and education.degree is None:
                education.degree = degree.group(0).strip(" ,")
                before, after = piece[: degree.start()], piece[degree.end() :]
                education.field = _clean_field(after)
                # "B.Tech, IIT Delhi" or "IIT Delhi, B.Tech": the school shares the piece.
                for part in (*before.split(","), *after.split(",")):
                    if has_school_word(part) and education.school is None:
                        education.school = part.strip(" ,;:-")
            elif has_school_word(piece) and education.school is None:
                school = piece
                if _GRADE.search(school):
                    school = re.split(r",", school)[0]
                education.school = school.strip(" ,;:-")
            elif education.degree is not None and education.field is None:
                education.field = _clean_field(piece)
    return education


def parse_education(lines: list[Line]) -> list[ParsedEducation]:
    entries = [_read(entry) for entry in _split_entries(lines)]
    return [entry for entry in entries if entry.school or entry.degree]
