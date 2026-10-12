"""Score maths. Pure functions, no I/O, so every number is testable and
explainable: the model supplies verdicts, this file turns them into a score.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

Verdict = Literal["strong", "partial", "missing"]

REQUIRED_POINTS: dict[Verdict, float] = {"strong": 2, "partial": 1, "missing": 0}
NICE_TO_HAVE_POINTS: dict[Verdict, float] = {"strong": 1, "partial": 0.5, "missing": 0}

# How far short of the required years the candidate is -> the highest score allowed.
_SLIGHTLY_SHORT_YEARS = 1.0
_SLIGHTLY_SHORT_CAP = 75
_WELL_SHORT_CAP = 60


@dataclass(frozen=True)
class Judged:
    required: bool
    verdict: Verdict


def compute_score(results: Sequence[Judged]) -> int:
    earned = 0.0
    possible = 0.0
    for result in results:
        table = REQUIRED_POINTS if result.required else NICE_TO_HAVE_POINTS
        earned += table[result.verdict]
        possible += table["strong"]
    if possible == 0:
        return 0
    return round(earned / possible * 100)


def _month_index(year_month: str) -> int:
    year, month = year_month.split("-")
    return int(year) * 12 + int(month) - 1


def years_of_experience(periods: Sequence[tuple[str, str | None]], today: date) -> float:
    """Total years covered by (start, end) 'YYYY-MM' periods, counting overlapping
    jobs once. An end of None means the role is current.
    """
    now = today.year * 12 + today.month - 1
    spans = sorted(
        (_month_index(start), min(_month_index(end), now) + 1 if end else now + 1)
        for start, end in periods
    )
    months = 0
    covered_until: int | None = None
    for start, end in spans:
        if end <= start:
            continue
        if covered_until is None or start > covered_until:
            months += end - start
            covered_until = end
        elif end > covered_until:
            months += end - covered_until
            covered_until = end
    return round(months / 12, 1)


def apply_seniority_cap(
    score: int, *, min_years: int | None, candidate_years: float
) -> tuple[int, str | None]:
    """Skills can match while experience does not; cap the score and say why."""
    if not min_years or candidate_years >= min_years:
        return score, None

    shortfall = min_years - candidate_years
    cap = _SLIGHTLY_SHORT_CAP if shortfall <= _SLIGHTLY_SHORT_YEARS else _WELL_SHORT_CAP
    shown_years = f"{candidate_years:g}"
    if score <= cap:
        return score, (
            f"This role asks for {min_years}+ years of experience; "
            f"your profile shows about {shown_years}."
        )
    return cap, (
        f"This role asks for {min_years}+ years of experience and your profile shows about "
        f"{shown_years}, so the score is capped at {cap} (your skills alone scored {score})."
    )


ExperienceStatus = Literal["meets", "short", "well_short", "open_to_freshers", "not_stated"]


@dataclass(frozen=True)
class ExperienceResult:
    """Where the candidate stands on experience. Produced for every job, so the
    question is never silently skipped.
    """

    status: ExperienceStatus
    required_min: float | None
    required_max: float | None
    candidate_years: float
    # "stated", "preferred", "title" (worked out from the job title) or "fresher".
    source: str | None
    quote: str | None
    summary: str


def _years(value: float) -> str:
    if 0 < value < 1:
        months = round(value * 12)
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{value:g} year{'s' if value != 1 else ''}"


def score_cap(status: str, source: str | None) -> int | None:
    """The highest score a job check may show for this experience verdict, or
    None when experience does not limit it. Also used to tell the app what the
    limit is, so it can show what ticking more skills would do to the score.
    """
    if status == "well_short":
        return _WELL_SHORT_CAP if source == "stated" else _SLIGHTLY_SHORT_CAP
    if status == "short":
        return _SLIGHTLY_SHORT_CAP
    return None


def check_experience(
    score: int,
    *,
    required_min: float | None,
    required_max: float | None = None,
    source: str | None,
    quote: str | None = None,
    candidate_years: float,
    includes_internships: bool = False,
) -> tuple[int, ExperienceResult]:
    """Compares the experience a job asks for with the candidate's, caps the
    score when they fall short, and always returns a sentence saying so.
    """
    have = (
        "no dated work experience yet"
        if candidate_years <= 0
        else f"about {_years(candidate_years)}"
        + (", internships included" if includes_internships else "")
    )

    def result(
        status: ExperienceStatus, summary: str, capped: int = score
    ) -> tuple[int, ExperienceResult]:
        return capped, ExperienceResult(
            status=status,
            required_min=required_min,
            required_max=required_max,
            candidate_years=candidate_years,
            source=source,
            quote=quote,
            summary=summary,
        )

    if source is None or required_min is None:
        return result(
            "not_stated",
            "This posting does not say how many years of experience it wants. "
            f"Your profile shows {have}. Check the listing before you apply.",
        )
    if source == "fresher" or required_min <= 0:
        upper = f" (up to {_years(required_max)})" if required_max else ""
        return result(
            "open_to_freshers",
            f"Open to freshers{upper}: no prior experience is required. Your profile shows {have}.",
        )

    wanted = (
        f"{required_min:g} to {_years(required_max)}"
        if required_max and required_max > required_min
        else f"{required_min:g}+ year{'s' if required_min != 1 else ''}"
        if required_min >= 1
        else f"at least {_years(required_min)}"
    )
    asks = {
        "stated": f"This role asks for {wanted} of experience",
        "preferred": f"This role prefers {wanted} of experience",
        "title": (
            f"The title says “{quote}”, which usually means around {wanted} of experience "
            "(the posting gives no number)"
        ),
    }.get(source, f"This role asks for {wanted} of experience")

    if candidate_years >= required_min:
        return result("meets", f"{asks}. Your profile shows {have}, so you meet it.")

    shortfall = required_min - candidate_years
    # A number worked out from the title, or one the posting only prefers, is
    # softer than a stated requirement: it never caps harder than "slightly short".
    well_short = shortfall > _SLIGHTLY_SHORT_YEARS
    cap = score_cap("well_short" if well_short else "short", source)
    assert cap is not None  # both of those statuses carry a cap
    capped = min(score, cap)
    cap_note = (
        f" Your score is capped at {cap} because of this (your skills alone scored {score})."
        if capped < score
        else ""
    )
    if well_short:
        return result(
            "well_short",
            f"{asks}. Your profile shows {have}. That is a big gap: employers usually screen "
            f"on experience before they look at skills, so treat this as a long shot.{cap_note}",
            capped,
        )
    return result(
        "short",
        f"{asks}. Your profile shows {have}. You are close, but expect to be asked about it."
        f"{cap_note}",
        capped,
    )
