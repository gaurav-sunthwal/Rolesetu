"""Finds the Skills section of a resume PDF and reads how it is laid out:
where each line ends, which font it uses, and how the skills are separated.
"""

import re
import statistics
from dataclasses import dataclass
from typing import Any, Literal

import pymupdf

_HEADING = re.compile(
    r"^(?:(?:technical|core|key|professional|relevant)\s+)?"
    r"(?:skills?(?:\s*(?:&|and)\s*\w+)?|technologies|tech(?:nical)?\s+stack|"
    r"technical\s+proficienc(?:y|ies)|areas?\s+of\s+expertise|competenc(?:e|ies))\s*:?$",
    re.IGNORECASE,
)
_OTHER_HEADING = re.compile(
    r"^(?:(?:professional|work|relevant)\s+)?(?:experience|employment|projects?|education|"
    r"certifications?|achievements?|awards?|summary|profile|objective|languages|interests|"
    r"publications|references|contact|selected\s+projects|work\s+history)\b",
    re.IGNORECASE,
)
_LABEL = re.compile(r"^([A-Z][^:]{1,38}):(?:\s|$)")
_SEPARATORS = (", ", " | ", " • ", " · ", "; ")
# A line this far right of the heading belongs to another column.
_MAX_INDENT = 40.0
# Pieces closer than this (as a share of the font size) belong to the same line.
_JOIN_WITHIN = 0.6


@dataclass(frozen=True)
class Span:
    text: str
    font: str
    size: float
    color: int
    x0: float
    x1: float
    baseline: float


@dataclass(frozen=True)
class Line:
    spans: tuple[Span, ...]
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans).replace("\xa0", " ").strip()

    @property
    def baseline(self) -> float:
        return self.spans[0].baseline

    @property
    def last_span(self) -> Span:
        """The last span with ink in it: the style new text continues in."""
        return next(span for span in reversed(self.spans) if span.text.strip())

    @property
    def style(self) -> tuple[str, float]:
        first = next(span for span in self.spans if span.text.strip())
        return (first.font, round(first.size, 1))


@dataclass
class Entry:
    """One row of the section, such as "Languages: Python, SQL", with any wrapped lines."""

    label: str | None
    lines: list[Line]

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def last(self) -> Line:
        return self.lines[-1]

    @property
    def wrap_x(self) -> float:
        """Where a wrapped line starts: under the existing wrapped lines if there are any."""
        return self.lines[1].x0 if len(self.lines) > 1 else self.lines[0].x0


@dataclass
class SkillsSection:
    page_index: int
    heading: Line
    entries: list[Entry]
    separator: str
    # Distance between one line's baseline and the next.
    leading: float
    # The furthest right a line in this column may reach.
    right_limit: float
    # False when another column sits beside this one, so nothing may be pushed down.
    can_grow: bool
    kind: Literal["labelled", "list"]


class NoSkillsSectionError(Exception):
    pass


class UnsupportedLayoutError(Exception):
    pass


def read_lines(page: pymupdf.Page) -> list[Line]:
    lines: list[Line] = []
    blocks: list[dict[str, Any]] = page.get_text("dict")["blocks"]
    for block in blocks:
        for raw in block.get("lines", []):
            spans = tuple(
                Span(
                    text=span["text"],
                    font=span["font"],
                    size=span["size"],
                    color=span["color"],
                    x0=span["bbox"][0],
                    x1=span["bbox"][2],
                    baseline=span["origin"][1],
                )
                for span in raw["spans"]
            )
            if not any(span.text.strip() for span in spans):
                continue
            x0, y0, x1, y1 = raw["bbox"]
            lines.append(Line(spans=spans, x0=x0, y0=y0, x1=x1, y1=y1))
    lines.sort(key=lambda line: (round(line.baseline, 1), line.x0))

    # Text added to a line later (by this tool, or by a PDF editor) is stored as
    # its own piece beside the original. Pieces that touch on the same baseline
    # are one line to the reader, so they are joined into one here.
    joined: list[Line] = []
    for line in lines:
        previous = joined[-1] if joined else None
        if (
            previous is not None
            and abs(previous.baseline - line.baseline) < 0.5
            and -1.0 <= line.x0 - previous.x1 < previous.last_span.size * _JOIN_WITHIN
        ):
            joined[-1] = Line(
                spans=previous.spans + line.spans,
                x0=previous.x0,
                y0=min(previous.y0, line.y0),
                x1=line.x1,
                y1=max(previous.y1, line.y1),
            )
        else:
            joined.append(line)
    return joined


def _separator_of(text: str) -> str:
    counts = {separator: text.count(separator) for separator in _SEPARATORS}
    best = max(counts, key=lambda separator: counts[separator])
    return best if counts[best] > 0 else ", "


def _section_on(page_index: int, lines: list[Line]) -> SkillsSection | None:
    heading = next(
        (line for line in lines if len(line.text) <= 40 and _HEADING.match(line.text)), None
    )
    if heading is None:
        return None

    column = [
        line
        for line in lines
        if line.baseline > heading.baseline + 1
        and heading.x0 - 3 <= line.x0 <= heading.x0 + _MAX_INDENT
    ]
    if not column:
        return None
    # A heading set in its own style ends the section when that style returns.
    # A heading that looks like body text can only be told by its wording.
    distinct = heading.style != column[0].style
    body: list[Line] = []
    for line in column:
        if (distinct and line.style == heading.style) or (
            len(line.text) <= 40 and _OTHER_HEADING.match(line.text)
        ):
            break
        body.append(line)
    if not body:
        return None

    entries: list[Entry] = []
    for line in body:
        match = _LABEL.match(line.text)
        if match:
            entries.append(Entry(label=match.group(1).strip(), lines=[line]))
        elif entries:
            entries[-1].lines.append(line)
    kind: Literal["labelled", "list"] = "labelled"
    text = " ".join(line.text for line in body)
    if not entries:
        if not any(separator in text for separator in _SEPARATORS):
            raise UnsupportedLayoutError
        entries, kind = [Entry(label=None, lines=body)], "list"

    def gaps_between(lines: list[Line]) -> list[float]:
        return [
            after.baseline - before.baseline
            for before, after in zip(lines, lines[1:], strict=False)
            if 0.8 * before.last_span.size
            < after.baseline - before.baseline
            < 2.2 * before.last_span.size
        ]

    # A wrapped line often sits closer than the next row does, so the spacing
    # is taken from lines that wrapped whenever the section has any.
    wrapped = [gap for entry in entries for gap in gaps_between(entry.lines)]
    gaps = wrapped or gaps_between(body)
    leading = statistics.median(gaps) if gaps else body[0].last_span.size * 1.25

    left = min(line.x0 for line in body)
    same_column = [
        line for line in lines if left - 15 <= line.x0 <= left + _MAX_INDENT and line.x1 > line.x0
    ]
    right_limit = max(line.x1 for line in same_column)
    beside = any(line.x0 > right_limit + 5 or line.x1 < left - 5 for line in lines)

    return SkillsSection(
        page_index=page_index,
        heading=heading,
        entries=entries,
        separator=_separator_of(text),
        leading=leading,
        right_limit=right_limit,
        can_grow=not beside,
        kind=kind,
    )


def find_skills_section(doc: pymupdf.Document) -> SkillsSection:
    for index in range(doc.page_count):
        section = _section_on(index, read_lines(doc[index]))
        if section is not None:
            return section
    raise NoSkillsSectionError
