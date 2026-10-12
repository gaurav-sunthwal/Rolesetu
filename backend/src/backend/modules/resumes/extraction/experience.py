"""Work history: finds each role, then its title, company, place, dates and
the description under it.

A role is anchored on its date range ("Jun 2023 – Present"), because that is
the one thing nearly every resume writes for every job. The few short lines
around the dates are the role's header; everything until the next header is
its description.
"""

import re
from dataclasses import dataclass, field

from backend.modules.resumes.extraction import dates
from backend.modules.resumes.extraction.keywords import (
    has_company_word,
    has_title_word,
    is_place,
)
from backend.modules.resumes.extraction.lines import (
    Line,
    fragments,
    is_bullet,
    join_wrapped,
    looks_like_sentence,
)
from backend.modules.resumes.parsed import ParsedExperience

_MAX_HEADER_LINES = 4
_ACTION_START = re.compile(
    r"^(?:\w+ed|built|led|ran|wrote|won|made|drove|grew|cut|set|own|owns|lead|leads|work|works|"
    r"working|responsible|develop|design|manage|maintain|create|implement|collaborat\w*|"
    r"using|handl\w*|support\w*)\b",
    re.IGNORECASE,
)


@dataclass
class _Entry:
    header: list[Line] = field(default_factory=list)
    body: list[Line] = field(default_factory=list)
    has_dates: bool = False


def _has_range(line: Line) -> bool:
    return dates.find_range(line.flat) is not None and not looks_like_sentence(
        dates.remove(line.flat, dates.find_range(line.flat))  # type: ignore[arg-type]
    )


def _has_single_date(line: Line) -> bool:
    text = line.flat
    return (
        dates.find_single(text) is not None
        and len(text.split()) <= 9
        and (line.bold or line.lead_bold or has_title_word(text) or has_company_word(text))
    )


def looks_like_header_text(text: str) -> bool:
    """Short, name-like text: "Globex Labs", "Senior Engineer", "Pune, India"."""
    words = text.split()
    if not words or len(words) > 9 or text.rstrip().endswith(".") and len(words) > 3:
        return False
    if _ACTION_START.match(text):
        return False
    if has_title_word(text) or has_company_word(text):
        return True
    if any(is_place(piece) for piece in fragments(text)):
        return True
    significant = [word for word in words if len(word) > 3]
    if not significant:
        return len(words) <= 3
    capitalised = sum(1 for word in significant if word[0].isupper() or word[0].isdigit())
    return capitalised / len(significant) >= 0.7


def _is_detail_line(line: Line) -> bool:
    """A line under the title that lists short facts, one of them a place:
    "ScrollShop (commerce app) | Pune, India | Google Play".
    """
    pieces = fragments(line.text)
    return (
        len(pieces) >= 2
        and any(is_place(piece) for piece in pieces)
        and all(len(piece.split()) <= 8 for piece in pieces)
    )


def _split_entries(lines: list[Line]) -> list[_Entry]:
    styled = any(line.bold or line.lead_bold for line in lines)
    anchored = any(_has_range(line) for line in lines)

    def is_anchor(line: Line) -> bool:
        return _has_range(line) or (anchored is False and _has_single_date(line))

    def is_header(line: Line, after_header: bool) -> bool:
        if is_bullet(line):
            return False
        if is_anchor(line):
            return True
        if after_header and _is_detail_line(line):
            return True
        if styled:
            # In a resume that bolds its titles, trust the bold; a plain line
            # only counts when it directly continues a header.
            return (
                line.bold or line.lead_bold or (after_header and looks_like_header_text(line.flat))
            )
        return looks_like_header_text(line.flat)

    entries: list[_Entry] = []
    current: _Entry | None = None
    pending: list[Line] = []

    for line in lines:
        header_open = (
            current is not None and not current.body and len(current.header) < _MAX_HEADER_LINES
        )
        if is_header(line, after_header=header_open or bool(pending)):
            anchor = is_anchor(line)
            if anchor:
                if current is not None and header_open and not current.has_dates and not pending:
                    current.header.append(line)
                    current.has_dates = True
                else:
                    current = _Entry(header=[*pending, line], has_dates=True)
                    entries.append(current)
                pending = []
            elif current is not None and header_open and current.has_dates and not pending:
                current.header.append(line)
            elif not anchored and (line.bold or line.lead_bold or not styled) and not pending:
                # No dates anywhere in this section: each title starts a role.
                if current is not None and header_open and not current.body:
                    current.header.append(line)
                else:
                    current = _Entry(header=[line])
                    entries.append(current)
            else:
                pending = [*pending, line][-(_MAX_HEADER_LINES - 1) :]
            continue

        if pending:
            if styled and all(item.bold or item.lead_bold for item in pending):
                # A bold title with no dates of its own is still a separate role.
                current = _Entry(header=pending)
                entries.append(current)
            elif current is not None:
                # Header-looking plain lines that were not followed by dates were prose.
                current.body.extend(pending)
            pending = []
        if current is not None:
            current.body.append(line)

    if pending and current is not None:
        current.body.extend(pending)
    return entries


def _split_title_company(piece: str) -> list[str]:
    """ "Data Analyst, Northwind Traders" and "Engineer at Acme" are two parts."""
    at = re.split(r"\s+at\s+", piece, maxsplit=1, flags=re.IGNORECASE)
    if len(at) == 2 and has_title_word(at[0]):
        return [at[0].strip(), at[1].strip()]
    if "," not in piece or is_place(piece):
        return [piece]
    head, _, tail = piece.rpartition(",")
    head, tail = head.strip(), tail.strip()
    if is_place(tail) and not is_place(head):
        return [*_split_title_company(head), tail]
    first, _, rest = piece.partition(",")
    first, rest = first.strip(), rest.strip()
    if (
        rest
        and has_title_word(first) != has_title_word(rest)
        and not re.match(r"^(?:inc|ltd|llc|llp|pvt|co)\b", rest, re.IGNORECASE)
    ):
        return [first, *_split_title_company(rest)]
    return [piece]


def _read_header(header: list[Line]) -> tuple[ParsedExperience, list[str]]:
    """The role, plus any header text that was not its title, employer or place
    (a product name, say). That text is kept as the first line of the description.
    """
    found: dates.DateRange | None = None
    pieces: list[str] = []
    for line in header:
        text = line.text
        line_dates = dates.find_range(text) if found is None else None
        if line_dates is None and found is None and len(line.flat.split()) <= 9:
            line_dates = dates.find_single(text)
        if line_dates is not None:
            found = line_dates
            text = dates.remove(text, line_dates)
        for piece in fragments(text):
            pieces.extend(part for part in _split_title_company(piece) if part)

    # "(Remote)" -> "Remote", but "App (beta)" keeps its brackets.
    pieces = [
        piece[1:-1].strip() if re.fullmatch(r"[(\[][^()\[\]]*[)\]]", piece) else piece
        for piece in pieces
    ]
    pieces = [piece for piece in pieces if piece and re.search(r"[A-Za-z]", piece)]

    location = next((piece for piece in pieces if is_place(piece)), None)
    rest = [piece for piece in pieces if piece != location]
    title = next((piece for piece in rest if has_title_word(piece)), None)
    rest = [piece for piece in rest if piece != title]
    company = next((piece for piece in rest if has_company_word(piece)), None) or (
        rest[0] if rest else None
    )
    if title is None:
        others = [piece for piece in rest if piece != company]
        if others:
            # No recognisable job-title word: the piece that is not the employer.
            title = others[0]
        elif company is not None and not has_company_word(company):
            title, company = company, None

    used = {title, company, location}
    extra = [piece for piece in pieces if piece not in used]
    experience = ParsedExperience(title=title, company=company, location=location)
    if found is not None:
        if found.start is None:
            # A single date ("May 2023"): the role is placed at that month.
            experience.start = experience.end = found.end
        else:
            experience.start, experience.end = found.start, found.end
            experience.is_current = found.is_current
    return experience, extra


def parse_experience(lines: list[Line]) -> list[ParsedExperience]:
    roles: list[ParsedExperience] = []
    for entry in _split_entries(lines):
        role, extra = _read_header(entry.header)
        body = join_wrapped(entry.body)
        role.description = "\n".join(part for part in (" | ".join(extra), body) if part) or None
        if role.title or role.company:
            roles.append(role)
    return roles
