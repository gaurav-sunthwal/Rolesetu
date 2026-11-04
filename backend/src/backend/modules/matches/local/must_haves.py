"""Hard requirements: licences, certifications, clearances and degrees in a
named subject that a posting says a candidate must hold.

These are screened before anything else: a hospital cannot hire a nurse
without a nursing licence however good their skills are. Only requirements
the posting states as required are taken; "preferred" or "a plus" ones are
left to the skills list. Each one is checked against the whole profile, and a
missing one caps the score (see `scoring.MUST_HAVE_CAP`).
"""

import re
from dataclasses import dataclass

from backend.modules.profiles.schemas import ProfileRead

_SOFT = re.compile(
    r"preferred|a plus|is a plus|nice to have|desirable|bonus|ideally|advantage|"
    r"or equivalent|or related|or similar|or a related|equivalent experience|"
    r"would be (?:great|nice|helpful)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Rule:
    name: str
    # How the posting asks for it.
    asked: re.Pattern[str]
    # How a profile shows it.
    held: re.Pattern[str]


def _rule(name: str, asked: str, held: str | None = None) -> _Rule:
    return _Rule(
        name,
        re.compile(asked, re.IGNORECASE),
        re.compile(held or asked, re.IGNORECASE),
    )


_RULES: tuple[_Rule, ...] = (
    _rule(
        "Professional Engineer (PE) license",
        r"professional engineer(?:ing)?\s*\(?pe\)?|\bpe licen[cs]e|\bp\.e\.",
        r"professional engineer|\bpe\b|\bp\.e\.",
    ),
    _rule(
        "Registered Nurse (RN) license",
        r"registered nurse\s*\(?rn\)?\s*licen[cs]e|\brn licen[cs]e|active (?:rn|registered nurse)",
        r"registered nurse|\brn\b|nursing",
    ),
    _rule("CPA", r"\bcpa\b(?! or)", r"\bcpa\b|certified public accountant"),
    _rule(
        "Chartered Accountant (CA)",
        r"chartered accountant|\bca\b(?= (?:qualified|required|certification))",
        r"chartered accountant|\bca\b|\bicai\b",
    ),
    _rule(
        "Security clearance",
        r"security clearance|\bts/sci\b|secret clearance|top secret",
        r"clearance|\bts/sci\b|top secret",
    ),
    # Not every mention of OSHA: "follow OSHA standards" is not a certificate.
    _rule(
        "OSHA certification",
        r"\bosha\s*(?:10|30)\b|\bosha (?:certification|certified|card)",
        r"\bosha\b",
    ),
    _rule("PMP certification", r"\bpmp\b", r"\bpmp\b|project management professional"),
    _rule(
        "Bar admission",
        r"admitted to (?:the|a) bar|bar admission|licensed attorney|enrolled advocate",
        r"\bbar\b|attorney|advocate|lawyer|\bllb\b|\bll\.b",
    ),
)

# "Bachelor's degree in Electrical Engineering", "B.Tech in Mechanical Engineering"
_DEGREE = re.compile(
    r"(?<![A-Za-z])(?i:bachelor'?s?|master'?s?|b\.?\s?s\.?c?\.?|b\.?\s?e\.?|b\.?\s?tech|"
    r"m\.?\s?s\.?|m\.?\s?tech|degree|diploma)(?![A-Za-z])[^\n;]{0,30}?\bin\s+"
    r"(?P<subjects>[A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+)*"
    r"(?:\s*(?:,|or|/)\s*[A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+)*)*)",
)
# Words that name the kind of subject, not the subject itself.
_GENERIC = frozenset({"engineering", "science", "sciences", "studies", "technology", "management"})


@dataclass(frozen=True)
class MustHave:
    name: str
    held: bool
    # The posting's own words.
    quote: str
    # Where the profile shows it, when it does.
    evidence: str | None


def _sentences(text: str) -> list[str]:
    # A full stop ends a sentence only after a real word, so "B.E." and "e.g." do not.
    parts = re.split(r"(?<=[a-z]{4}[.!?])\s+(?=[A-Z])|;\s*|\n+", text)
    return [part.strip(" -•*\t") for part in parts if part.strip()]


def _profile_texts(profile: ProfileRead) -> list[tuple[str, str]]:
    """(where, text) for every part of the profile a qualification can appear in."""
    texts = [("Headline", profile.headline or "")]
    texts += [
        (f"Education: {item.school}", f"{item.degree} {item.field or ''}")
        for item in profile.education
    ]
    texts += [("Listed skill", item.name) for item in profile.skills]
    texts += [
        (f"{item.title} at {item.company}", f"{item.title}\n{item.description}")
        for item in profile.experience
    ]
    texts += [(f"Project: {item.name}", item.description) for item in profile.projects]
    return [(where, text) for where, text in texts if text.strip()]


def _subjects(raw: str) -> list[str]:
    """The key word of each subject: "Electrical Engineering or Physics" -> electrical, physics."""
    found: list[str] = []
    for subject in re.split(r"\s*(?:,|\bor\b|/)\s*", raw):
        words = [word.lower() for word in subject.split() if word.lower() not in _GENERIC]
        if words:
            found.append(words[0])
    return found


def find_must_haves(jd_text: str, profile: ProfileRead) -> list[MustHave]:
    texts = _profile_texts(profile)
    found: list[MustHave] = []
    seen: set[str] = set()
    for sentence in _sentences(jd_text):
        if _SOFT.search(sentence):
            continue
        for rule in _RULES:
            if rule.name in seen or not rule.asked.search(sentence):
                continue
            seen.add(rule.name)
            where = next((place for place, text in texts if rule.held.search(text)), None)
            found.append(MustHave(rule.name, where is not None, sentence[:200], where))
        degree = _DEGREE.search(sentence)
        if degree is None:
            continue
        subjects = _subjects(degree.group("subjects"))
        if not subjects or "degree" in seen:
            continue
        seen.add("degree")
        studied = [
            (f"Education: {item.school}", f"{item.degree} {item.field or ''}".lower())
            for item in profile.education
        ]
        where = next(
            (place for place, text in studied if any(word in text for word in subjects)), None
        )
        name = f"Degree in {degree.group('subjects').strip()}"
        found.append(MustHave(name[:60], where is not None, sentence[:200], where))
    return found
