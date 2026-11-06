"""Finds skills in text using the dictionary in `catalog_data`.

`find_skills` is the one entry point: it returns every skill mentioned in a
piece of text with its position. Both the job description and the profile go
through it, so the two are compared on identical terms.

Optional `catalog_append` adds domain-specific lines (same `name | aliases | group`
format) for fields outside software and data.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from backend.modules.matches.local.catalog_data import CATALOG, FIELD_SHOWS, IMPLIES


@dataclass(frozen=True)
class Skill:
    name: str
    group: str | None = None
    # Read from the posting's wording ("knowledge of X"), not from the
    # dictionary (see `phrases`). Judged by the words it shares with the profile.
    phrase: bool = False
    # False for skills recognised only because the candidate listed the name.
    catalog: bool = True


@dataclass(frozen=True)
class Mention:
    skill: Skill
    start: int
    end: int


@dataclass(frozen=True)
class _Index:
    pattern: re.Pattern[str]
    # lower-cased term -> skill
    by_term: dict[str, Skill]
    # lower-cased term -> the exact spellings accepted (for "!" names)
    exact_only: dict[str, frozenset[str]]
    by_name: dict[str, Skill]


def _compile(terms: list[str]) -> re.Pattern[str]:
    ordered = sorted(set(terms), key=lambda term: (-len(term), term))
    body = "|".join(re.escape(term) for term in ordered)
    return re.compile(rf"(?<![A-Za-z0-9.+#])(?:{body})(?![A-Za-z0-9+#])", re.IGNORECASE)


def _parse_catalog_lines(
    text: str,
    *,
    by_term: dict[str, Skill],
    exact_only: dict[str, set[str]],
    by_name: dict[str, Skill],
) -> None:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        name, aliases, group = parts[0], parts[1], (parts[2] if len(parts) > 2 else "")
        strict = name.startswith("!")
        name = name.lstrip("!")
        skill = Skill(name=name, group=group or None, catalog=True)
        by_name[name.lower()] = skill
        if strict:
            exact_only.setdefault(name.lower(), set()).add(name)
        by_term.setdefault(name.lower(), skill)
        for alias in filter(None, (alias.strip() for alias in aliases.split(","))):
            by_term.setdefault(alias.lower(), skill)


def _build(extra_names: tuple[str, ...], catalog_append: str) -> _Index:
    by_term: dict[str, Skill] = {}
    exact_only: dict[str, set[str]] = {}
    by_name: dict[str, Skill] = {}

    _parse_catalog_lines(CATALOG, by_term=by_term, exact_only=exact_only, by_name=by_name)
    if catalog_append.strip():
        _parse_catalog_lines(
            catalog_append, by_term=by_term, exact_only=exact_only, by_name=by_name
        )

    for name in extra_names:
        cleaned = name.strip()
        if 1 < len(cleaned) <= 60 and cleaned.lower() not in by_term:
            skill = Skill(name=cleaned, catalog=False)
            by_term[cleaned.lower()] = skill
            by_name[cleaned.lower()] = skill

    return _Index(
        pattern=_compile(list(by_term)),
        by_term=by_term,
        exact_only={term: frozenset(spellings) for term, spellings in exact_only.items()},
        by_name=by_name,
    )


@lru_cache(maxsize=64)
def _index(extra_names: tuple[str, ...], catalog_append: str) -> _Index:
    return _build(extra_names, catalog_append)


def find_skills(
    text: str, extra_names: tuple[str, ...] = (), catalog_append: str = ""
) -> list[Mention]:
    index = _index(extra_names, catalog_append)
    mentions: list[Mention] = []
    for match in index.pattern.finditer(text):
        term = match.group(0)
        allowed = index.exact_only.get(term.lower())
        if allowed is not None and term not in allowed:
            continue
        mentions.append(Mention(index.by_term[term.lower()], match.start(), match.end()))
    return mentions


def in_dictionary(skill: Skill, catalog_append: str = "") -> bool:
    """True for a skill the dictionary knows (base or domain append), not a
    profile-only name or a phrase requirement.
    """
    if skill.phrase or not skill.catalog:
        return False
    entry = _index((), catalog_append).by_name.get(skill.name.lower())
    return entry is not None and entry.catalog


def lookup(name: str, extra_names: tuple[str, ...] = (), catalog_append: str = "") -> Skill | None:
    return _index(extra_names, catalog_append).by_term.get(name.strip().lower())


@lru_cache(maxsize=1)
def _implications() -> dict[Skill, tuple[Skill, ...]]:
    by_name = _index((), "").by_name
    table: dict[Skill, tuple[Skill, ...]] = {}
    for raw in IMPLIES.splitlines():
        if "->" not in raw:
            continue
        left, right = raw.split("->", 1)
        source = by_name.get(left.strip().lower())
        if source is None:
            continue
        implied = tuple(
            skill
            for name in right.split(",")
            if (skill := by_name.get(name.strip().lower())) is not None
        )
        if implied:
            table[source] = implied
    return table


def implied_by(skill: Skill) -> tuple[Skill, ...]:
    return _implications().get(skill, ())


@lru_cache(maxsize=1)
def _field_skills() -> dict[str, tuple[Skill, ...]]:
    by_name = _index((), "").by_name
    return {
        field: tuple(by_name[n.lower()] for n in names if n.lower() in by_name)
        for field, names in FIELD_SHOWS.items()
    }


def shown_by_field(field_key: str) -> tuple[Skill, ...]:
    return _field_skills().get(field_key, ())
