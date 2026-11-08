"""Reads how much experience a job posting asks for.

Postings say this in many ways: "3+ years", "2-5 Yrs", "minimum two years",
"freshers welcome", "6 months", or only through the title ("Senior ..."). A
number of years that is about something else (the company's age, a bond, a
contract, or the education duration) is not taken for an experience requirement.
"""

import re
from dataclasses import dataclass
from typing import Literal

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15,
}  # fmt: skip
_NUMBER = rf"(\d{{1,2}}(?:\.\d)?|{'|'.join(_WORDS)})"
_AMOUNT = re.compile(
    rf"(?<![\d.$₹/])\b{_NUMBER}\s*(?:\+|plus)?\s*"
    rf"(?:(?:-|–|—|to)\s*{_NUMBER}\s*(?:\+|plus)?\s*)?"
    r"(years?|yrs?|yoe|months?|mos)\b(?!\s+old)",
    re.IGNORECASE,
)
# The sentence must be talking about the candidate's experience...
_ABOUT_EXPERIENCE = re.compile(
    r"experienc|\bexp\b|\byoe\b|background|track record|hands[- ]on|"
    r"work(?:ed|ing)? (?:with|in|on|as)|in (?:a |an )?(?:similar|related|comparable) role|"
    r"professional|industry|proficien|expertise|"
    r"(?:years?|yrs?) (?:of|in|with|as|building|developing|designing|writing|working)",
    re.IGNORECASE,
)
# Standalone range or pill indicating experience ("3-6 Years", "0 - 2 yrs", "2 to 5 years").
_RANGE = re.compile(
    rf"\b{_NUMBER}\s*(?:\+|plus)?\s*(?:-|–|—|to)\s*{_NUMBER}\s*(?:\+|plus)?\s*(?:years?|yrs?|yoe|months?|mos)\b",
    re.IGNORECASE,
)
# Metadata tag / pill with a plus or standalone year amount ("5+ years", "3+ Yrs").
_PILL = re.compile(
    rf"(?:^|[|•·,\t/])\s*{_NUMBER}\s*(?:\+|plus)?\s*(?:years?|yrs?|yoe)\s*(?:$|[|•·,\t/])|"
    rf"\b{_NUMBER}\s*(?:\+|plus)\s*(?:years?|yrs?|yoe)\b",
    re.IGNORECASE,
)
# ...and not about one of these.
_ABOUT_SOMETHING_ELSE = re.compile(
    r"founded|established|in business|years? ago|anniversary|\bbond\b|contract|agreement|"
    r"warranty|probation|notice period|duration|stipend|\bctc\b|salary|\blpa\b|per (?:year|annum)|"
    r"(?:a|each|every) year|over the (?:next|last|past)|years? of age|financial year|fiscal|"
    r"\bbatch\b|pass(?:ed)?[- ]out|graduat(?:ed|ing) (?:in|within)|"
    r"for (?:over |more than )?\d+ years,? we",
    re.IGNORECASE,
)
# Education/schooling duration — "15 years full time education", "10+2+3 = 15 years of study",
# "educational qualification: 12 years", "schooling: 10 years", "full-time education".
# These describe years spent in the school system, not years of professional work.
_ABOUT_EDUCATION = re.compile(
    r"educational? (?:qualification|background|requirement|standard|level|degree)|"
    r"(?:full[- ]time|full[- ]time\s+)?education\b|"
    r"\bschooling\b|"
    r"\bstudy(?:ing)?\b|"
    r"\bcourse(?:work)?\b|"
    r"\bclass(?:room)?\b|"
    r"years? of (?:education|study|schooling|learning|training)|"
    r"(?:secondary|primary|higher|formal|academic) (?:education|schooling|qualification)|"
    r"(?:class|grade|standard)\s+\d+|"  # "Class 12", "Grade 10", "Standard 10"
    r"\b(?:10th|12th|ssc|hsc|cbse|icse|igcse|gcse|a[- ]levels?|o[- ]levels?)\b|"
    r"\b(?:bachelor|b\.?tech|b\.?e|b\.?sc|b\.?com|b\.?a|m\.?tech|m\.?sc|mba|phd|doctorate)\b",
    re.IGNORECASE,
)
_PREFERRED = re.compile(
    r"prefer|nice to have|good to have|bonus|\ba plus\b|ideal|desirable", re.IGNORECASE
)
_FRESHER = re.compile(
    r"\bfreshers?\b|entry[- ]level|recent graduates?|new grads?|fresh graduates?|"
    r"no (?:prior |previous |work )?experience (?:is )?(?:required|needed|necessary)",
    re.IGNORECASE,
)
# What a title usually implies when the posting gives no number.
_TITLE_LEVELS: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"\b(intern|internship|trainee|apprentice|graduate)\b", re.I), "fresher", 0),
    (re.compile(r"\b(junior|jr|associate|entry[- ]level)\b", re.I), "fresher", 0),
    (re.compile(r"\b(lead|staff|principal|architect|head)\b", re.I), "title", 7),
    (re.compile(r"\b(senior|sr)\b", re.I), "title", 5),
)

Source = Literal["stated", "preferred", "title", "fresher"]


@dataclass(frozen=True)
class ExperienceAsk:
    """What the job wants. `source` is None when the posting gives no clue at all."""

    min_years: float | None = None
    max_years: float | None = None
    source: Source | None = None
    # The posting's own words, or the title word the estimate came from.
    quote: str | None = None


def _value(text: str) -> float:
    return float(_WORDS.get(text.lower(), 0) or text)


def _is_experience_sentence(sentence: str) -> bool:
    if _ABOUT_SOMETHING_ELSE.search(sentence):
        return False
    # A sentence about the candidate's schooling duration is not a work-experience
    # requirement, even when it contains a number followed by "years".
    # e.g. "Educational Qualification: 15 years full time education"
    #      "B.Tech or equivalent (10+2+3 = 15 years of education)"
    if _ABOUT_EDUCATION.search(sentence):
        return False
    if _ABOUT_EXPERIENCE.search(sentence) or _RANGE.search(sentence):
        return True
    return bool(len(sentence) <= 60 and _PILL.search(sentence))


def _sentences(text: str) -> list[str]:
    """Sentences to read. Job sites often print a label on one line and its
    value on the next ("Experience" / "2 - 5 years"); those are joined.
    """
    parts: list[str] = []
    previous = ""
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if len(previous) <= 40 and len(line) <= 40 and _ABOUT_EXPERIENCE.search(previous):
            line = f"{previous}: {line}"
        parts += [
            part.strip() for part in re.split(r"(?<=[.!?;])\s+|[|•·\t]", line) if part.strip()
        ]
        previous = line
    return parts


def read_experience(jd_text: str, title: str | None = None) -> ExperienceAsk:
    required: list[ExperienceAsk] = []
    preferred: list[ExperienceAsk] = []
    for sentence in _sentences(jd_text):
        if not _is_experience_sentence(sentence):
            continue
        for match in _AMOUNT.finditer(sentence):
            low, high, unit = match.group(1), match.group(2), match.group(3).lower()
            per_year = 12.0 if unit.startswith("mo") else 1.0
            least = round(_value(low) / per_year, 1)
            most = round(_value(high) / per_year, 1) if high else None
            if least > 30 or (most is not None and most < least):
                continue
            wanted = _PREFERRED.search(sentence) is not None
            found = ExperienceAsk(
                min_years=least,
                max_years=most,
                source="preferred" if wanted else "stated",
                quote=sentence[:200],
            )
            (preferred if wanted else required).append(found)

    # "5+ years overall, 2+ with React": the largest minimum is the real bar.
    for group in (required, preferred):
        if group:
            return max(group, key=lambda ask: ask.min_years or 0.0)

    fresher = _FRESHER.search(jd_text)
    if fresher:
        return ExperienceAsk(min_years=0, source="fresher", quote=fresher.group(0))
    for pattern, source, years in _TITLE_LEVELS:
        word = pattern.search(title or "")
        if word:
            return ExperienceAsk(
                min_years=years,
                source="fresher" if source == "fresher" else "title",
                quote=word.group(0),
            )
    return ExperienceAsk()
