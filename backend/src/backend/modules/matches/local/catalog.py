"""Finds skills in text using the dictionary in `catalog_data`.

`find_skills` is the one entry point: it returns every skill mentioned in a
piece of text with its position. Both the job description and the profile go
through it, so the two are compared on identical terms.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from backend.modules.matches.local.catalog_data import CATALOG, IMPLIES


@dataclass(frozen=True)
class Skill:
    name: str
    group: str | None = None


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
    # Longest first, so "React Native" is tried before "React" and "Node.js"
    # before "Node". The guards stop "Java" matching inside "JavaScript" and
    # "C" matching the start of "C++" or "C#".
    ordered = sorted(set(terms), key=lambda term: (-len(term), term))
    body = "|".join(re.escape(term) for term in ordered)
    return re.compile(rf"(?<![A-Za-z0-9.+#])(?:{body})(?![A-Za-z0-9+#])", re.IGNORECASE)


def _build(extra_names: tuple[str, ...]) -> _Index:
    by_term: dict[str, Skill] = {}
    exact_only: dict[str, set[str]] = {}
    by_name: dict[str, Skill] = {}

    for raw in CATALOG.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        name, aliases, group = parts[0], parts[1], (parts[2] if len(parts) > 2 else "")
        strict = name.startswith("!")
        name = name.lstrip("!")
        skill = Skill(name=name, group=group or None)
        by_name[name.lower()] = skill
        if strict:
            exact_only.setdefault(name.lower(), set()).add(name)
        by_term.setdefault(name.lower(), skill)
        for alias in filter(None, (alias.strip() for alias in aliases.split(","))):
            by_term.setdefault(alias.lower(), skill)

    # Skills the candidate lists that the dictionary does not know are still
    # recognised by name, so a niche tool on their profile is found in a job.
    for name in extra_names:
        cleaned = name.strip()
        if 1 < len(cleaned) <= 60 and cleaned.lower() not in by_term:
            skill = Skill(name=cleaned)
            by_term[cleaned.lower()] = skill
            by_name[cleaned.lower()] = skill

    return _Index(
        pattern=_compile(list(by_term)),
        by_term=by_term,
        exact_only={term: frozenset(spellings) for term, spellings in exact_only.items()},
        by_name=by_name,
    )


@lru_cache(maxsize=64)
def _index(extra_names: tuple[str, ...]) -> _Index:
    return _build(extra_names)


def find_skills(text: str, extra_names: tuple[str, ...] = ()) -> list[Mention]:
    index = _index(extra_names)
    mentions: list[Mention] = []
    for match in index.pattern.finditer(text):
        term = match.group(0)
        allowed = index.exact_only.get(term.lower())
        # "Go" the language, not "go" the verb; "Express", not "express".
        if allowed is not None and term not in allowed:
            continue
        mentions.append(Mention(index.by_term[term.lower()], match.start(), match.end()))
    return mentions


def lookup(name: str, extra_names: tuple[str, ...] = ()) -> Skill | None:
    """The dictionary entry for a skill name or alias, if there is one."""
    return _index(extra_names).by_term.get(name.strip().lower())


@lru_cache(maxsize=1)
def _implications() -> dict[Skill, tuple[Skill, ...]]:
    by_name = _index(()).by_name
    table: dict[Skill, tuple[Skill, ...]] = {}
    for raw in IMPLIES.splitlines():
        if "->" not in raw:
            continue
        left, right = raw.split("->", 1)
        source = by_name[left.strip().lower()]
        table[source] = tuple(by_name[name.strip().lower()] for name in right.split(","))
    return table


def implied_by(skill: Skill) -> tuple[Skill, ...]:
    """Skills that using `skill` demonstrates (Tailwind CSS shows CSS)."""
    return _implications().get(skill, ())
