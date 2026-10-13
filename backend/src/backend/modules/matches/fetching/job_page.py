"""Reads a job out of a listing page's HTML.

Most job boards embed a schema.org `JobPosting` block (it is how they get into
Google's job search). That block gives the title, company, description, skills,
location and salary as labelled fields, so nothing has to be guessed. When a
page has no such block, the visible text is used instead.
"""

import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

_LD_JSON = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "table", "blockquote", "dt", "dd",
}  # fmt: skip
_SKIPPED_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}
_EMPLOYMENT = {
    "FULL_TIME": "Full time", "PART_TIME": "Part time", "CONTRACTOR": "Contract",
    "TEMPORARY": "Temporary", "INTERN": "Internship", "VOLUNTEER": "Volunteer",
    "PER_DIEM": "Per diem", "OTHER": "Other",
}  # fmt: skip
MIN_DESCRIPTION_LENGTH = 200
# A page title such as "34 Work From Home Jobs in Oct 2026" is a search result.
_LIST_TITLE = re.compile(
    r"^\s*[\d,]+\+?\s+.*\b(?:jobs?|internships?|openings|vacancies)\b|"
    r"\b(?:jobs|internships|vacancies)\s+(?:in|for|near)\b",
    re.IGNORECASE,
)
# Wording a single job's page has and a list of jobs usually does not.
_JOB_BODY_CUE = re.compile(
    r"responsibilit|requirements?|qualifications?|what you(?:'ll| will)|about the (?:role|job)|"
    r"skills? required|who can apply|key skills|job description|we are looking for",
    re.IGNORECASE,
)


@dataclass
class JobPage:
    title: str | None = None
    company: str | None = None
    description: str = ""
    location: str | None = None
    employment_type: str | None = None
    salary: str | None = None
    posted_on: str | None = None
    skills: list[str] = field(default_factory=list)
    # "structured" when read from the page's JobPosting block, else "page text".
    source: str = "structured"

    def as_text(self) -> str:
        """The description the scorer reads, with listed skills made explicit."""
        text = self.description
        missing = [skill for skill in self.skills if skill.lower() not in text.lower()]
        if missing:
            text = f"{text}\n\nSkills required: {', '.join(missing)}"
        return text.strip()


class _TextExtractor(HTMLParser):
    """HTML to plain text: one line per block, skipping scripts and page chrome."""

    def __init__(self, skip_chrome: bool) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = _SKIPPED_TAGS if skip_chrome else {"script", "style"}
        self._depth = 0
        self._parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skip:
            self._depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip:
            self._depth = max(0, self._depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        lines = (
            re.sub(r"[ \t ]+", " ", line).strip() for line in "".join(self._parts).splitlines()
        )
        return "\n".join(line for line in lines if line)


def html_to_text(markup: str, *, skip_chrome: bool = False) -> str:
    parser = _TextExtractor(skip_chrome)
    parser.feed(markup)
    return parser.text()


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = html.unescape(value).strip()
        return cleaned or None
    return None


def _types(node: dict[str, Any]) -> list[str]:
    kind = node.get("@type")
    return [str(item) for item in kind] if isinstance(kind, list) else [str(kind)]


def _find_posting(data: Any) -> dict[str, Any] | None:
    """Walks lists and @graph wrappers to the first JobPosting."""
    if isinstance(data, list):
        for item in data:
            if (found := _find_posting(item)) is not None:
                return found
    elif isinstance(data, dict):
        if "JobPosting" in _types(data):
            return data
        if "@graph" in data:
            return _find_posting(data["@graph"])
    return None


def _location(posting: dict[str, Any]) -> str | None:
    places: list[str] = []
    raw = posting.get("jobLocation")
    for place in raw if isinstance(raw, list) else [raw]:
        address = place.get("address") if isinstance(place, dict) else None
        if isinstance(address, dict):
            parts = [
                _text(address.get(key))
                for key in ("addressLocality", "addressRegion", "addressCountry")
            ]
            label = ", ".join(part for part in parts if part)
        else:
            label = _text(address) or ""
        # Some sites fill an unknown location with a placeholder such as "-".
        if re.search(r"[^\W\d_]", label) and label not in places:
            places.append(label)
    where = " / ".join(places[:3]) or None
    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return f"Remote ({where})" if where else "Remote"
    return where


def _amount(value: Any) -> str:
    """230000.0 reads as "230,000"; anything that is not a number is left alone."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int | float) else str(value)


def _salary(posting: dict[str, Any]) -> str | None:
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return None
    value = base.get("value")
    currency = _text(base.get("currency")) or ""
    if isinstance(value, dict):
        low, high = value.get("minValue"), value.get("maxValue")
        amount = value.get("value")
        unit = str(value.get("unitText", "")).lower()
        if low is not None and high is not None and low != high:
            figure = f"{_amount(low)} to {_amount(high)}"
        else:
            single = low if low is not None else (high if high is not None else amount)
            if single is None:
                return None
            figure = _amount(single)
        # "Not disclosed" in the amount field is not a salary.
        if not re.search(r"\d", figure):
            return None
        return " ".join(part for part in (currency, figure, f"per {unit}" if unit else "") if part)
    if isinstance(value, int | float) or (isinstance(value, str) and re.search(r"\d", value)):
        return f"{currency} {value}".strip()
    return None


def _skills(posting: dict[str, Any]) -> list[str]:
    raw = posting.get("skills")
    if isinstance(raw, str):
        items = re.split(r"[,;\n]", html_to_text(raw))
    elif isinstance(raw, list):
        items = [str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in raw]
    else:
        return []
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))[:60]


def _from_posting(posting: dict[str, Any]) -> JobPage:
    organisation = posting.get("hiringOrganization")
    company = (
        _text(organisation.get("name")) if isinstance(organisation, dict) else _text(organisation)
    )

    sections: list[str] = []
    description = html_to_text(str(posting.get("description") or ""))
    if description:
        sections.append(description)
    # Some sites put these in their own fields instead of the description.
    for key, heading in (
        ("responsibilities", "Responsibilities"),
        ("qualifications", "Requirements"),
        ("experienceRequirements", "Experience"),
        ("educationRequirements", "Education"),
    ):
        value = posting.get(key)
        extra = html_to_text(value) if isinstance(value, str) else ""
        # Experience is often given as data ({"monthsOfExperience": 24}), not as text.
        if key == "experienceRequirements" and isinstance(value, dict):
            months = value.get("monthsOfExperience")
            if isinstance(months, int | float) and months >= 0:
                extra = (
                    "No prior experience required."
                    if months == 0
                    else f"{months:g} months of experience required."
                )
        if extra and extra[:80] not in description:
            sections.append(f"{heading}:\n{extra}")

    kinds = posting.get("employmentType")
    kind = kinds[0] if isinstance(kinds, list) and kinds else kinds
    return JobPage(
        title=_text(posting.get("title")),
        company=company,
        description="\n\n".join(sections),
        location=_location(posting),
        employment_type=_EMPLOYMENT.get(str(kind).upper()) if kind else None,
        salary=_salary(posting),
        posted_on=(_text(posting.get("datePosted")) or "")[:10] or None,
        skills=_skills(posting),
    )


def read_job_page(markup: str) -> JobPage | None:
    """The job on this page, or None if no job description can be found."""
    for block in _LD_JSON.findall(markup):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        posting = _find_posting(data)
        if posting is not None:
            page = _from_posting(posting)
            if len(page.description) >= MIN_DESCRIPTION_LENGTH:
                return page

    # No structured block: fall back to the page's readable text, but only when
    # it reads like one job. A search page full of listings must not be scored
    # as though it were a single role.
    parser = _TextExtractor(skip_chrome=True)
    parser.feed(markup)
    text = parser.text()
    if len(text) < MIN_DESCRIPTION_LENGTH * 2 or is_job_list(markup):
        return None
    if not _JOB_BODY_CUE.search(text):
        return None
    title = re.split(r"\s+[|\u2013\u2014-]\s+", parser.title.strip())[0].strip() or None
    return JobPage(title=title, description=text[:20000], source="page text")


def is_job_list(markup: str) -> bool:
    """True for a search or category page that lists many jobs."""
    for block in _LD_JSON.findall(markup):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        if any(isinstance(node, dict) and "ItemList" in _types(node) for node in nodes):
            return True
    title = re.search(r"<title[^>]*>(.*?)</title>", markup, re.IGNORECASE | re.DOTALL)
    return bool(title and _LIST_TITLE.search(html.unescape(title.group(1))))
