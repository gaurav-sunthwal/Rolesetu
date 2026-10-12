"""Decides which row of the Skills section a new skill belongs in, using the
skills dictionary: "GraphQL" goes beside the other backend skills, "Kotlin"
beside the other languages. No model is involved.
"""

import re
from collections.abc import Sequence
from functools import lru_cache

from backend.modules.matches.local.catalog import find_skills
from backend.modules.matches.local.catalog_data import CATALOG

# Words a resume uses in a row's label, for each part of the dictionary.
_LABEL_WORDS = {
    "languages": r"language",
    "web frontend": r"front|web|framework|librar|ui",
    "mobile": r"mobile|android|ios|app",
    "backend": r"back|framework|librar|server|api",
    "databases": r"data|database|storage|\bdb\b",
    "cloud and devops": r"cloud|devops|tool|platform|infra|release|deploy",
    "testing": r"test|quality|practice",
    "data and ML": r"data|\bml\b|\bai\b|machine|analytic",
    "design and product": r"design|product|tool",
    "practices": r"practice|method|process|other|soft",
}
_CATCH_ALL = re.compile(r"tool|other|misc|additional|technolog", re.IGNORECASE)


@lru_cache(maxsize=1)
def _areas() -> dict[str, str]:
    """Canonical skill name (lower-cased) -> the part of the dictionary it is listed under."""
    areas: dict[str, str] = {}
    area = ""
    for raw in CATALOG.splitlines():
        line = raw.strip()
        if line.startswith("# ---"):
            area = line.removeprefix("# ---").strip()
        elif line and not line.startswith("#"):
            areas[line.split("|")[0].strip().lstrip("!").lower()] = area
    return areas


def area_of(skill: str) -> str | None:
    mentions = find_skills(skill)
    name = mentions[0].skill.name if mentions else skill
    return _areas().get(name.lower())


def rank_rows(skill: str, rows: Sequence[tuple[str | None, str]]) -> list[tuple[int, float]]:
    """(row number, score) pairs, best home for `skill` first. Each row is
    (label, text). A score of zero means nothing ties the skill to that row.
    """
    area = area_of(skill)
    scores: list[float] = []
    for label, text in rows:
        score = 0.0
        if area:
            neighbours = [mention.skill.name.lower() for mention in find_skills(text)]
            score += sum(1 for name in neighbours if _areas().get(name) == area)
            if label and re.search(_LABEL_WORDS.get(area, r"$^"), label, re.IGNORECASE):
                score += 3
        if label and _CATCH_ALL.search(label):
            score += 0.5
        scores.append(score)
    order = sorted(range(len(rows)), key=lambda index: -scores[index])
    return [(index, scores[index]) for index in order]


def already_listed(skill: str, text: str) -> bool:
    wanted = {mention.skill.name.lower() for mention in find_skills(skill)} or {skill.lower()}
    listed = {mention.skill.name.lower() for mention in find_skills(text)}
    return (
        bool(wanted & listed)
        or re.search(rf"(?<![\w+#]){re.escape(skill)}(?![\w+#])", text, re.IGNORECASE) is not None
    )
