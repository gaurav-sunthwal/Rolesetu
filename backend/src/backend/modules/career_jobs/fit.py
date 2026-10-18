"""Which jobs a user is shown, by experience.

A job is shown when it asks for no more than the user has (a fit), or for up
to one year more (a stretch, always labelled as one). Jobs asking for more are
not shown at all. Jobs well below the user's level are left out too: a
five-year engineer is not looking for fresher roles.
"""

from dataclasses import dataclass
from typing import Literal

# How far above their own experience a user is still shown a job.
STRETCH_YEARS = 1.0
# A posting gives only a minimum: assume it is for people up to this much above it.
OPEN_RANGE_YEARS = 3.0
# "Freshers welcome" with no upper number: for people with up to this much.
FRESHER_CEILING_YEARS = 2.0

FitKind = Literal["fits", "stretch", "not_stated"]


@dataclass(frozen=True)
class Fit:
    kind: FitKind
    note: str


def _years(value: float) -> str:
    if 0 < value < 1:
        months = round(value * 12)
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{value:g} year{'s' if value != 1 else ''}"


def _asks(min_years: float, max_years: float | None) -> str:
    if min_years <= 0:
        return "freshers" + (f" (up to {_years(max_years)})" if max_years else "")
    if max_years and max_years > min_years:
        return f"{min_years:g}–{_years(max_years)}"
    return f"{_years(min_years)}+"


def fit_for(
    candidate_years: float,
    *,
    min_years: float | None,
    max_years: float | None,
    source: str | None,
) -> Fit | None:
    """How the job sits against the user's experience, or None to leave it out."""
    if source is None or min_years is None:
        return Fit("not_stated", "The posting does not say how much experience it wants.")

    fresher = source == "fresher" or min_years <= 0
    low = 0.0 if fresher else min_years
    if max_years is not None and max_years >= low:
        ceiling = max_years
    else:
        ceiling = FRESHER_CEILING_YEARS if fresher else low + OPEN_RANGE_YEARS
    if candidate_years > ceiling:
        return None

    have = "no work experience yet" if candidate_years <= 0 else f"about {_years(candidate_years)}"
    wanted = _asks(low, max_years)
    if low <= candidate_years:
        return Fit("fits", f"Asks for {wanted}; you have {have}.")
    if low - candidate_years <= STRETCH_YEARS:
        return Fit(
            "stretch",
            f"A stretch: asks for {wanted} and you have {have}. Worth applying if your skills fit.",
        )
    return None
