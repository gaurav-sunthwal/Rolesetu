"""Projects: a name, the tech it lists, a link, and the description under it."""

import re
from dataclasses import dataclass, field

from backend.modules.resumes.extraction import dates
from backend.modules.resumes.extraction.contact import links_in
from backend.modules.resumes.extraction.experience import looks_like_header_text
from backend.modules.resumes.extraction.lines import (
    Line,
    fragments,
    is_bullet,
    join_wrapped,
    strip_bullet,
)
from backend.modules.resumes.parsed import ParsedProject

_TECH_LABEL = re.compile(
    r"^(?:tech(?:nical)?\s*stack|technolog(?:y|ies)(?:\s+used)?|tools(?:\s+used)?|stack|"
    r"built\s+(?:with|using)|tech|skills(?:\s+used)?|languages|frameworks|environment)\s*[:\-–]\s*",
    re.IGNORECASE,
)
_URL_TEXT = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)+/\S+", re.IGNORECASE)
_LINK_WORD = re.compile(
    r"^(?:(?:live|view|source|project)\s+)?(?:link|github|gitlab|demo|live|source|code|repo|"
    r"repository|website|site|view|url|app|play\s+store|app\s+store|google\s+play)$",
    re.IGNORECASE,
)


@dataclass
class _Entry:
    header: Line
    body: list[Line] = field(default_factory=list)


def _tech_list(text: str) -> list[str]:
    items = [item.strip(" .") for item in re.split(r"[,;|/•·]|\s+and\s+", text)]
    return [item for item in items if item and len(item) <= 40 and len(item.split()) <= 4]


def _split_entries(lines: list[Line]) -> list[_Entry]:
    styled = any(line.bold or line.lead_bold for line in lines)
    entries: list[_Entry] = []
    for index, line in enumerate(lines):
        following = lines[index + 1] if index + 1 < len(lines) else None
        if is_bullet(line) or _TECH_LABEL.match(line.flat):
            starts = False
        elif styled:
            starts = line.bold or line.lead_bold
        else:
            # Unstyled resume: a short name-like line that has text under it.
            starts = (
                looks_like_header_text(
                    dates.remove(line.flat, found)
                    if (found := dates.find_dates(line.flat))
                    else line.flat
                )
                and following is not None
                and (not entries or bool(entries[-1].body))
            )
        if starts:
            entries.append(_Entry(header=line))
        elif entries:
            entries[-1].body.append(line)
    return entries


def _is_tech_line(line: Line) -> bool:
    """ "Expo | Next.js | TypeScript | PostgreSQL": three or more short items."""
    if is_bullet(line):
        return False
    pieces = fragments(line.text)
    return len(pieces) >= 3 and all(len(piece.split()) <= 4 for piece in pieces)


def _read(entry: _Entry) -> ParsedProject:
    header = entry.header.text
    found = dates.find_dates(header)
    if found is not None:
        header = dates.remove(header, found)
    header = _URL_TEXT.sub(" ", header)

    pieces = [piece for piece in fragments(header) if not _LINK_WORD.match(piece)]
    name, _, inline_tech = (pieces[0] if pieces else "").partition(":")
    name = name.strip(" (),")
    tech: list[str] = _tech_list(inline_tech) if inline_tech.strip() else []
    taglines: list[str] = []
    trailing = pieces[1:]
    # Several short pieces after the name are a tech list ("App | React, Node").
    # A single phrase is the project's tagline, which belongs in the description.
    listed = len(trailing) >= 3 and all(len(piece.split()) <= 4 for piece in trailing)
    for piece in trailing:
        if listed or "," in piece:
            tech.extend(_tech_list(piece))
        else:
            taglines.append(piece)

    body: list[Line] = []
    for index, line in enumerate(entry.body):
        text = strip_bullet(line.flat)
        label = _TECH_LABEL.match(text)
        if label:
            tech.extend(_tech_list(text[label.end() :]))
        elif index == 0 and not tech and _is_tech_line(line):
            tech.extend(piece.strip(" .") for piece in fragments(line.text))
        else:
            body.append(line)

    links = links_in([entry.header, *entry.body])
    description = "\n".join(part for part in (*taglines, join_wrapped(body)) if part)
    return ParsedProject(
        name=name or None,
        tech=list(dict.fromkeys(item for item in tech if item)),
        description=description or None,
        url=links[0] if links else None,
    )


def parse_projects(lines: list[Line]) -> list[ParsedProject]:
    projects = [_read(entry) for entry in _split_entries(lines)]
    return [project for project in projects if project.name]
