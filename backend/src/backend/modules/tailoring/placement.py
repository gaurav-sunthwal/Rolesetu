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
    "languages": r"language|code|programming|script|technical|software",
    "web frontend": r"front|web|framework|librar|ui|frontend|technical|software",
    "mobile": r"mobile|android|ios|app|technical|software",
    "backend": r"back|framework|librar|server|api|backend|technical|software",
    "databases": r"data|database|storage|\bdb\b|sql|technical|software",
    "cloud and devops": (
        r"cloud|devops|tool|platform|infra|release|deploy|technical|software|it\b|tech"
    ),
    "testing": r"test|quality|practice|qa\b|technical|software",
    "data and ML": r"data|\bml\b|\bai\b|machine|analytic|analysis|analytics|quantitative",
    "design and product": r"design|product|tool|ux|ui",
    "practices": (
        r"practice|method|process|other|soft|interpersonal|communication|teamwork|leadership|professional"
    ),
    "office tools": r"office|productivity|admin|administrative|suite|word|excel|spreadsheet|tools",
    "electrical and automation": r"electrical|electronics|automation|hardware|scada|plc|technical",
    "mechanical and manufacturing": r"mechanical|manufacturing|production|cad|solidworks|technical",
    "construction and civil": r"construction|civil|structural|site|survey",
    "healthcare": r"health|medical|clinical|nursing|patient|care",
    "accounting and finance": r"finance|financial|accounting|audit|tax|payroll|bookkeep",
    "marketing": r"marketing|brand|seo|sem|social media|content|growth",
    "sales": r"sales|crm|client|business dev|account|lead",
    "HR": (
        r"hr\b|human resources?|recruit|talent|personnel|onboard|"
        r"people|administrative|admin|employee"
    ),
    "operations": (
        r"operation|logistics|supply chain|procurement|inventory|operations|organis|organiz"
    ),
}
_CATCH_ALL = re.compile(r"tool|other|misc|additional|technolog", re.IGNORECASE)

_ROW_HEURISTICS: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(r"hr|administrative|admin|people|personnel", re.IGNORECASE),
        re.compile(
            r"hr\b|onboard|recruit|talent|payroll|employee|personnel|interview|hiring|benefit|leave|induction|compliance",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"techn|software|it\b|stack|devops|cloud|tools?", re.IGNORECASE),
        re.compile(
            r"kubernetes|docker|cloud|aws|azure|gcp|python|java|react|sql|linux|git|node|api|c\+\+|html|css|devops|code|software|excel",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"organis|organiz|management|planning|coordination", re.IGNORECASE),
        re.compile(
            r"organis|organiz|planning|event|time management|coordination|"
            r"scheduling|calendar|multitask",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"interpersonal|soft|communication|relationship", re.IGNORECASE),
        re.compile(
            r"interpersonal|communication|teamwork|conflict|listening|negotiat|presentation|empathy|collaboration",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"analytic|analysis|research", re.IGNORECASE),
        re.compile(
            r"analytic|analysis|data|metric|report|evaluat|research|"
            r"critical thinking|problem solving",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"professional|core|competenc|business", re.IGNORECASE),
        re.compile(
            r"leadership|business|ethics|domain|decision|stakeholder|strategy|professional",
            re.IGNORECASE,
        ),
    ),
)


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
        if label:
            for row_pat, skill_pat in _ROW_HEURISTICS:
                if row_pat.search(label) and skill_pat.search(skill):
                    score += 4
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
