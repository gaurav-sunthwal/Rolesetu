"""Which line of work a job title belongs to, and how a job's field compares
with the fields a person has actually worked in.

Skills alone cannot tell an Electrical Design Manager from a Data Architect
when the only skill both mention is "data analysis". The title can. Fields are
read from titles with word lists, not a model, so every decision can be shown
and tested: "This is an electrical engineering role; your work has been in
data and analytics."

Order matters: the specific fields are tried first, so "Electrical Design
Manager" is electrical engineering, not design, and "Marketing Data Analyst"
is marketing rather than data.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

FitStatus = Literal["same", "related", "different", "unknown"]


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    pattern: re.Pattern[str]
    related: frozenset[str]


def _field(key: str, label: str, words: str, related: Iterable[str] = ()) -> Field:
    return Field(key, label, re.compile(rf"\b(?:{words})", re.IGNORECASE), frozenset(related))


FIELDS: tuple[Field, ...] = (
    _field(
        "electrical",
        "electrical engineering",
        r"electrical|electrician|power systems?|substation|switchgear|electronics? engineer",
        ("mechanical", "construction"),
    ),
    _field(
        "mechanical",
        "mechanical engineering",
        r"mechanical|hvac|automotive engineer|manufacturing engineer|production engineer|"
        r"cad (?:designer|engineer)|piping engineer",
        ("electrical", "construction"),
    ),
    _field(
        "construction",
        "construction and civil engineering",
        r"construction|civil engineer|site engineer|structural engineer|quantity surveyor|"
        r"site supervisor|building services",
        ("electrical", "mechanical"),
    ),
    _field(
        "healthcare",
        "healthcare",
        r"nurs(?:e|es|ing)\b|\brn\b|physician|doctor|medical officer|pharmacist|clinical|"
        r"therapist|surgeon|dentist|lab technician|paramedic|healthcare|caregiver|midwife",
    ),
    _field(
        "finance",
        "accounting and finance",
        r"accountant|accounting|accounts (?:executive|officer|manager)|finance|financial|"
        r"audit(?:or)?|tax\b|bookkeep|payroll|chartered|\bcpa\b|treasury|controller|"
        r"credit analyst|investment",
        ("data",),
    ),
    _field(
        "legal",
        "legal",
        r"legal|lawyer|attorney|counsel|paralegal|advocate|solicitor",
    ),
    _field(
        "education",
        "teaching and education",
        r"teacher|tutor|lecturer|professor|faculty|educator|instructor|principal",
    ),
    _field(
        "hr",
        "HR and recruiting",
        r"\bhr\b|human resources|recruit|talent acquisition|people (?:partner|operations)",
    ),
    _field(
        "sales",
        "sales",
        r"sales|account executive|business development|\bbde\b|account manager|"
        r"pre-?sales|inside sales|relationship manager",
        ("marketing",),
    ),
    _field(
        "marketing",
        "marketing",
        r"marketing|marketer|\bseo\b|\bsem\b|social media|brand|growth (?:manager|lead)|"
        r"copywriter|content (?:writer|strategist|marketing|manager)|communications|\bpr\b",
        ("sales", "data", "design"),
    ),
    _field(
        "operations",
        "operations and supply chain",
        r"supply chain|logistics|procurement|warehouse|operations (?:manager|executive)|"
        r"purchase (?:manager|executive)|inventory",
    ),
    _field(
        "support",
        "customer support",
        r"customer (?:support|service|success)|support (?:executive|associate)|call cent|"
        r"helpdesk|help desk",
        ("sales",),
    ),
    _field(
        "design",
        "design",
        r"\bui\b|\bux\b|product designer|graphic designer|visual designer|interaction designer|"
        r"web designer|designer",
        ("software", "marketing", "product"),
    ),
    _field(
        "product",
        "product management",
        r"product (?:manager|owner|lead|management)|\bapm\b",
        ("software", "design", "data"),
    ),
    _field(
        "data",
        "data and analytics",
        # Not "data center": that is a building, and its jobs are engineering ones.
        r"data(?!\s*cent)|analytics|\bbi\b|business intelligence|machine learning|\bml\b|\bai\b|"
        r"artificial intelligence|statistic|analyst",
        ("software", "product", "finance", "marketing"),
    ),
    _field(
        "software",
        "software engineering",
        r"software|developer|programmer|front[- ]?end|back[- ]?end|full[- ]?stack|"
        r"web (?:engineer|developer)|mobile|android|\bios\b|devops|\bsre\b|site reliability|"
        r"cloud engineer|platform engineer|\bqa\b|test(?:ing)? engineer|\bsdet\b|\bsde\b|"
        r"security engineer|embedded|it (?:support|administrator)|system administrator|"
        r"solutions? architect|cloud architect|tech(?:nical)? lead|engineering manager|"
        # What a fresher studied, when they have no roles yet.
        r"computer (?:science|engineering|applications)|information technology",
        ("data", "design", "product"),
    ),
)

_BY_KEY = {field.key: field for field in FIELDS}

# The fields the skills dictionary knows well enough to score alone. A job in
# any other field is read by the model, because the dictionary would only find
# the few skills the person already has, and score them as a perfect fit.
DICTIONARY_FIELDS = frozenset({"software", "data"})


def field_of(title: str | None) -> Field | None:
    """The field a job or role title belongs to, or None when it gives no clue."""
    if not title or not title.strip():
        return None
    for field in FIELDS:
        if field.pattern.search(title):
            return field
    return None


def fields_of_person(
    titles: list[tuple[str, str | None, str | None]],
    headline: str | None,
    education_fields: list[str],
) -> list[str]:
    """The fields a person has worked in, most recent first.

    `titles` are (title, start, end) for each role, with 'YYYY-MM' dates and an
    end of None for a current role. The headline counts as their own statement
    of their field. Someone with no roles yet is placed by what they studied.
    """

    def recency(item: tuple[str, str | None, str | None]) -> tuple[str, str]:
        _, start, end = item
        return (end or "9999-99", start or "")

    fields: list[str] = []
    for title, _, _ in sorted(titles, key=recency, reverse=True):
        if (found := field_of(title)) is not None:
            fields.append(found.key)
    if (found := field_of(headline)) is not None:
        fields.append(found.key)
    if not titles:
        for studied in education_fields:
            if (found := field_of(studied)) is not None:
                fields.append(found.key)
    return list(dict.fromkeys(fields))


def label(key: str) -> str:
    return _BY_KEY[key].label


def related(a: str, b: str) -> bool:
    return b in _BY_KEY[a].related or a in _BY_KEY[b].related


@dataclass(frozen=True)
class FieldFit:
    status: FitStatus
    job_field: str | None
    # The person's fields, most recent first.
    candidate_fields: tuple[str, ...]
    summary: str


def _a(label: str) -> str:
    return f"{'an' if label[:1].lower() in 'aeiou' else 'a'} {label}"


def compare(job_field: Field | None, candidate_fields: list[str]) -> FieldFit:
    """How the job's field sits against the fields the person has worked in."""
    fields = tuple(dict.fromkeys(candidate_fields))
    if job_field is None or not fields:
        return FieldFit("unknown", job_field.key if job_field else None, fields, "")

    theirs = ", ".join(label(key) for key in fields[:2])
    if job_field.key in fields:
        return FieldFit(
            "same",
            job_field.key,
            fields,
            f"This is {_a(job_field.label)} role, the field you work in.",
        )
    if any(related(job_field.key, key) for key in fields):
        return FieldFit(
            "related",
            job_field.key,
            fields,
            f"This is {_a(job_field.label)} role. Your work has been in {theirs}, a related "
            "field, so your skills carry over in part.",
        )
    return FieldFit(
        "different",
        job_field.key,
        fields,
        f"This is {_a(job_field.label)} role, but your work has been in {theirs}. "
        "Employers screen on relevant background first, so treat this as a long shot "
        "unless you are changing careers on purpose.",
    )
