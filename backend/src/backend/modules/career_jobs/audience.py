"""Who the morning run collects for.

Before reading any careers site, the run counts how many users sit in each
experience band, and only jobs for bands that have users are collected. With
no senior users, senior roles are not read at all; the first senior user to
sign up turns that band on the next morning.
"""

from dataclasses import dataclass
from datetime import date

from backend.modules.career_jobs.fit import STRETCH_YEARS
from backend.modules.matches.scoring import years_of_experience


@dataclass(frozen=True)
class Band:
    name: str
    # Years of experience, from `low` up to (not including) `high`.
    low: float
    high: float


BANDS: tuple[Band, ...] = (
    Band("fresher", 0, 1),
    Band("junior", 1, 3),
    Band("mid", 3, 6),
    Band("senior", 6, 10),
    Band("very senior", 10, 99),
)


def band_of(years: float) -> Band:
    return next(band for band in BANDS if years < band.high)


@dataclass(frozen=True)
class Audience:
    """How many users are in each band. Empty means "collect everything"
    (no users yet, or the database could not be read)."""

    counts: dict[str, int]

    @property
    def bands(self) -> list[Band]:
        return [band for band in BANDS if self.counts.get(band.name)]

    def wants(self, *, min_years: float | None, source: str | None) -> bool:
        """Whether any user's band could be shown a job asking for `min_years`.

        A job's minimum decides its band. Each band also takes jobs up to one
        year above it, the stretch roles the page shows. A posting that gives
        no number is always kept: we cannot tell who it is for.
        """
        bands = self.bands
        if not bands or min_years is None or source is None:
            return True
        asked = 0.0 if source == "fresher" else max(min_years, 0.0)
        return any(band.low <= asked < band.high + STRETCH_YEARS for band in bands)

    def describe(self) -> str:
        if not self.bands:
            return "No users with a profile yet: collecting every level."
        users = ", ".join(f"{self.counts.get(b.name, 0)} {b.name}" for b in BANDS)
        chosen = ", ".join(b.name for b in self.bands)
        return f"Users: {users}. Collecting for: {chosen}."


def audience_from(experience_lists: list[list[dict[str, str | None]]], today: date) -> Audience:
    counts: dict[str, int] = {}
    for experience in experience_lists:
        periods = [
            (item["start"], item.get("end"))
            for item in experience
            if isinstance(item, dict) and item.get("start")
        ]
        band = band_of(years_of_experience(periods, today))  # type: ignore[arg-type]
        counts[band.name] = counts.get(band.name, 0) + 1
    return Audience(counts)


EVERYONE = Audience({})
