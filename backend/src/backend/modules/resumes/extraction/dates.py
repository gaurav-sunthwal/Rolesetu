"""Finds dates and date ranges in resume text and normalises them to YYYY-MM."""

import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH_WORD = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_YEAR = r"(?:19[5-9]\d|20\d{2})"


def _date(n: int) -> str:
    """One date: "Jun 2023", "June, 2023", "Jun '23", "06/2023" or "2023"."""
    return (
        rf"(?:(?P<mon{n}>{_MONTH_WORD})\.?,?\s*(?:(?P<my{n}>{_YEAR})|'?(?P<my2{n}>\d{{2}})(?!\d))"
        rf"|(?P<num{n}>0?[1-9]|1[0-2])\s*[/.]\s*(?P<ny{n}>{_YEAR})"
        rf"|(?P<y{n}>{_YEAR}))"
    )


_PRESENT = r"(?P<present>present|current(?:ly)?|now|ongoing|till\s+date|to\s+date|today|till\s+now)"
_BETWEEN = r"\s*(?:-|\u2013|\u2014|\u2012|to|until|till|through|\u2192)\s*"

_RANGE = re.compile(
    rf"(?<![\w/]){_date(1)}{_BETWEEN}(?:{_date(2)}|{_PRESENT})(?![\w/])",
    re.IGNORECASE,
)
_SINGLE = re.compile(rf"(?<![\w/]){_date(1)}(?![\w/])", re.IGNORECASE)


@dataclass(frozen=True)
class DateRange:
    start: str | None
    end: str | None
    is_current: bool
    # Where in the text it was found, so the caller can cut it out.
    span: tuple[int, int]
    # True when the resume gave only years, so the month is our placeholder.
    year_only: bool = False

    @property
    def start_year(self) -> int | None:
        return int(self.start[:4]) if self.start else None

    @property
    def end_year(self) -> int | None:
        return int(self.end[:4]) if self.end else None


def _year_ok(year: int) -> bool:
    return 1950 <= year <= date.today().year + 8


def _read(match: re.Match[str], n: int) -> tuple[str | None, bool]:
    """Returns ('YYYY-MM', year_only) for the n-th date in a match."""
    groups = match.groupdict()
    if groups.get(f"mon{n}"):
        month = _MONTHS[groups[f"mon{n}"][:3].lower()]
        year = int(groups[f"my{n}"]) if groups.get(f"my{n}") else 2000 + int(groups[f"my2{n}"])
        return (f"{year:04d}-{month:02d}", False) if _year_ok(year) else (None, False)
    if groups.get(f"num{n}"):
        year = int(groups[f"ny{n}"])
        month = int(groups[f"num{n}"])
        return (f"{year:04d}-{month:02d}", False) if _year_ok(year) else (None, False)
    if groups.get(f"y{n}"):
        year = int(groups[f"y{n}"])
        return (f"{year:04d}-01", True) if _year_ok(year) else (None, True)
    return None, False


def find_range(text: str) -> DateRange | None:
    """The first date range in the text, such as "Jun 2023 – Present"."""
    for match in _RANGE.finditer(text):
        start, start_year_only = _read(match, 1)
        if start is None:
            continue
        if match.group("present"):
            return DateRange(start, None, True, match.span(), start_year_only)
        end, end_year_only = _read(match, 2)
        if end is None:
            continue
        if end < start:
            end = None
        return DateRange(start, end, False, match.span(), start_year_only and end_year_only)
    return None


def find_single(text: str) -> DateRange | None:
    """A lone date, such as a graduation year. Treated as an end date."""
    for match in _SINGLE.finditer(text):
        value, year_only = _read(match, 1)
        if value is not None:
            return DateRange(None, value, False, match.span(), year_only)
    return None


def find_dates(text: str) -> DateRange | None:
    return find_range(text) or find_single(text)


def remove(text: str, found: DateRange) -> str:
    start, end = found.span
    cut = f"{text[:start]} {text[end:]}"
    cut = re.sub(r"\(\s*\)|\[\s*\]", " ", cut)
    return re.sub(r"[ ]{2,}", " ", cut).strip(" ,;|–—-:\t")
