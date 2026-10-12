"""Skills from the skills section: one item per skill, with a level only when
the resume states one next to it.
"""

import re

from backend.modules.resumes.extraction.lines import Line, is_bullet, strip_bullet
from backend.modules.resumes.parsed import ParsedSkill

_SEPARATORS = ",;|\t\u2022\u00b7\u25cf\u25aa"
_DASH = re.compile(r"\s+[\u2013\u2014-]\s+|\s{3,}")
_LABEL = re.compile(r"^[^:,;|]{1,40}:\s*\S")
_LEVELS: dict[str, str] = {
    "beginner": "beginner", "basic": "beginner", "basics": "beginner", "novice": "beginner",
    "familiar": "beginner", "elementary": "beginner", "learning": "beginner",
    "intermediate": "intermediate", "proficient": "intermediate", "working": "intermediate",
    "competent": "intermediate", "good": "intermediate",
    "advanced": "advanced", "expert": "advanced", "fluent": "advanced", "strong": "advanced",
    "experienced": "advanced",
}  # fmt: skip
_PAREN = re.compile(r"\(([^()]*)\)\s*$")
_MAX_WORDS = 5
_MAX_LENGTH = 50


def _split_label(text: str) -> str:
    """Drops a category label: "Languages: Python, Go" -> "Python, Go"."""
    label, separator, rest = text.partition(":")
    if separator and rest.strip() and len(label.split()) <= 5:
        return rest
    return text


def _one(raw: str) -> ParsedSkill | None:
    name = raw.strip(" .\t")
    name = re.sub(r"^(?:and|&)\s+", "", name, flags=re.IGNORECASE)
    level: str | None = None

    paren = _PAREN.search(name)
    if paren:
        words = paren.group(1).lower().split()
        level = next((_LEVELS[word] for word in words if word in _LEVELS), None)
        if level is not None:
            name = name[: paren.start()].strip()

    if not name or len(name) > _MAX_LENGTH or len(name.split()) > _MAX_WORDS:
        return None
    if not re.search(r"[A-Za-z]", name):
        return None
    return ParsedSkill(name=name, level=level)  # type: ignore[arg-type]


def _split(text: str) -> list[str]:
    """Splits on separators, but never inside brackets:
    "Push Notifications (Expo, FCM), Android" is two skills, not three.
    """
    pieces: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and char in _SEPARATORS:
            pieces.append("".join(current))
            current = []
        else:
            current.append(char)
    pieces.append("".join(current))
    return [part for piece in pieces for part in _DASH.split(piece)]


def _logical_lines(lines: list[Line]) -> list[str]:
    """Joins a wrapped line back onto the one it continues."""
    texts = [strip_bullet(line.text) for line in lines]
    labelled = sum(1 for text in texts if _LABEL.match(text)) >= 2
    out: list[str] = []
    for line, text in zip(lines, texts, strict=True):
        previous = out[-1] if out else ""
        open_bracket = previous.count("(") > previous.count(")")
        # In a "Category: a, b, c" list, a line without a category continues the last one.
        continues = bool(out) and (
            open_bracket
            or previous.rstrip().endswith(",")
            or (labelled and not _LABEL.match(text) and not is_bullet(line))
        )
        if continues:
            out[-1] = f"{previous.rstrip()} {text}"
        else:
            out.append(text)
    return out


def parse_skills(lines: list[Line]) -> list[ParsedSkill]:
    skills: list[ParsedSkill] = []
    for text in _logical_lines(lines):
        for piece in _split(_split_label(text)):
            skill = _one(piece)
            if skill is not None:
                skills.append(skill)
    return skills
