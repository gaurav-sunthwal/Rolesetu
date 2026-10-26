"""Reads a resume PDF as sections of editable lines, and applies a person's
edits to the file in place: words changed, lines removed, lines added.

Changed and added text is written in the resume's own font, size and colour,
at the positions the resume already uses, so the page looks exactly as it did
except for the words that changed. Removing or adding a line moves what is
below it up or down by one line, as a word processor would.

Edits always start from the stored file, never from an earlier preview. Line
ids are the order lines are read in, so they stay valid until the resume is
replaced.
"""

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import pymupdf

from backend.modules.resume_editor import links
from backend.modules.resume_editor.links import LineLink
from backend.modules.tailoring.pdf import editor
from backend.modules.tailoring.pdf.fonts import LineFont, font_for
from backend.modules.tailoring.pdf.replace import CannotReplaceError, raw_text, replace_in_line
from backend.modules.tailoring.pdf.section import Line, Span, read_lines
from backend.modules.tailoring.pdf.shift import CannotShiftError

_HEADING = re.compile(
    r"^(?:(?:professional|work|technical|core|key|relevant|selected|academic|additional|"
    r"personal)\s+)?"
    r"(?:experience|employment(?:\s+history)?|work\s+history|internships?|projects?|education|"
    r"qualifications?|skills?(?:\s*(?:&|and)\s*\w+)?|technologies|tech(?:nical)?\s+stack|"
    r"technical\s+proficienc(?:y|ies)|competenc(?:e|ies)|areas?\s+of\s+expertise|summary|"
    r"profile|about(?:\s+me)?|objective|certifications?(?:\s*(?:&|and)\s*\w+)?|licen[cs]es|"
    r"achievements?|accomplishments|awards?(?:\s*(?:&|and)\s*\w+)?|honou?rs|publications?|"
    r"languages?|interests|hobbies|volunteer(?:ing)?(?:\s+experience)?|leadership|activities|"
    r"extra[- ]?curricular(?:\s+activities)?|positions?\s+of\s+responsibility|courses|"
    r"coursework|training|strengths|references|contact(?:\s+(?:me|details|information))?)$",
    re.IGNORECASE,
)
# A bullet, dash or star that starts a line, with the space after it.
_BULLET = re.compile(r"^\s*(?:[•●▪■◦○‣⁃∙·►▸➢✓✔*]|[-–—](?=\s))\s*")
# Headings further apart than this (in points) start different columns.
_COLUMN_GAP = 80.0
# The space kept between a line and the text beside it on the same baseline.
_GAP_TO_NEIGHBOUR = 6.0

# A shape as PyMuPDF describes it (see `Page.get_drawings`).
Drawing = dict[str, Any]

Reason = Literal["not_found", "no_room", "no_font", "unsafe", "mixed_style", "two_columns"]


@dataclass(frozen=True)
class EditableLine:
    id: str
    page: int
    line: Line
    # A bullet and the space after it, kept as it is when the words change.
    prefix: str
    # The words a person may change.
    text: str
    # Where `text` starts in `raw_text(line)`.
    start: int
    heading: bool
    # A bullet drawn as its own piece of text, just left of the line.
    bullet: Line | None
    # A bullet drawn as a shape (a dot or a square), just left of the line.
    marks: tuple[Drawing, ...]
    # Links over words of this line (a LinkedIn or GitHub address, a project link).
    links: tuple[LineLink, ...]
    # How far left and right the line may grow without touching other text.
    left_limit: float
    right_limit: float
    right_aligned: bool
    # Distance from this line's baseline to the next line's.
    leading: float


@dataclass
class Section:
    title: str
    lines: list[EditableLine] = field(default_factory=list)


@dataclass
class Layout:
    # (width, height) of each page, in points.
    pages: list[tuple[float, float]]
    sections: list[Section]
    # Pages laid out in two or more columns: lines cannot be added there,
    # because moving one column down would move the other with it.
    multi_column: set[int]

    def by_id(self) -> dict[str, EditableLine]:
        return {line.id: line for section in self.sections for line in section.lines}


@dataclass(frozen=True)
class ChangeText:
    line_id: str
    text: str


@dataclass(frozen=True)
class RemoveLine:
    line_id: str


@dataclass(frozen=True)
class AddLine:
    """A new line under `after_id`. Long text wraps.

    It looks like the line it goes under, or like `style_id` when given: a new
    project's title can be added under the last bullet of the one before it.
    """

    after_id: str
    text: str
    style_id: str | None = None


Edit = ChangeText | RemoveLine | AddLine


@dataclass(frozen=True)
class Outcome:
    applied: bool
    reason: Reason | None = None
    # False when the resume's font lacked a letter and a look-alike was used.
    exact_font: bool = True


class _Refused(Exception):
    def __init__(self, reason: Reason):
        self.reason: Reason = reason
        super().__init__(reason)


class _Undo(Exception):
    """One edit cannot be made safely; the file is rebuilt without it."""

    def __init__(self, index: int, reason: Reason):
        self.index = index
        self.reason = reason
        super().__init__(reason)


def _plain(line: Line) -> str:
    return raw_text(line).replace("\xa0", " ")


def _is_heading_text(text: str) -> bool:
    words = re.sub(r"\s+", " ", text.strip().rstrip(":")).strip()
    return len(words) <= 45 and _HEADING.match(words) is not None


def _columns(headings: list[Line]) -> list[float]:
    """Where each column of the page starts, from where its headings start."""
    starts: list[float] = []
    for x in sorted(line.x0 for line in headings):
        if not starts or x - starts[-1] > _COLUMN_GAP:
            starts.append(x)
    return starts


def _column_of(x0: float, starts: list[float]) -> int:
    return max((index for index, start in enumerate(starts) if start <= x0 + 3), default=0)


def _leading(line: Line, column: list[Line]) -> float:
    """The spacing a new line under this one gets. A neighbour in the same
    style (the next bullet, say) shows it best; any close neighbour will do.
    """
    size = line.last_span.size
    above = [other for other in column if other.baseline < line.baseline - 1]
    below = [other for other in column if other.baseline > line.baseline + 1]
    nearest = [
        (other, abs(other.baseline - line.baseline))
        for other in (
            min(below, key=lambda other: other.baseline, default=None),
            max(above, key=lambda other: other.baseline, default=None),
        )
        if other is not None
    ]
    usable = [(other, gap) for other, gap in nearest if 0.8 * size < gap < 2.2 * size]
    alike = [gap for other, gap in usable if other.style == line.style]
    if alike or usable:
        return (alike or [gap for _, gap in usable])[0]
    return size * 1.25


def _marks_beside(line: Line, drawings: list[Drawing]) -> tuple[Drawing, ...]:
    """Small shapes just left of the line: bullets drawn as dots or squares."""
    middle = (line.y0 + line.y1) / 2
    return tuple(
        drawing
        for drawing in drawings
        if drawing["rect"].width <= 8
        and drawing["rect"].height <= 8
        and line.x0 - 25 <= drawing["rect"].x0
        and drawing["rect"].x1 <= line.x0 + 1
        and abs((drawing["rect"].y0 + drawing["rect"].y1) / 2 - middle) < line.last_span.size * 0.6
    )


def _read_page(doc: pymupdf.Document, number: int) -> tuple[list[EditableLine], list[float]]:
    lines = read_lines(doc[number])
    drawings: list[Drawing] = doc[number].get_drawings()
    line_links = links.read_links(doc[number], number, lines)
    plain = [_plain(line) for line in lines]
    bullets = {
        index
        for index, text in enumerate(plain)
        if text.strip() and not _BULLET.sub("", text).strip() and _BULLET.match(text)
    }

    word_headings = [line for line in lines if _is_heading_text(line.text)]
    # A heading with wording we do not know is found by sharing a known
    # heading's style, unless that style is simply the resume's body text.
    styles = Counter(line.style for line in lines)
    body_style = styles.most_common(1)[0][0] if styles else None
    heading_styles = {line.style for line in word_headings} - {body_style}
    headings = {
        id(line)
        for line in lines
        if _is_heading_text(line.text)
        or (
            line.style in heading_styles
            and len(line.text) <= 40
            and line.text[:1].isupper()
            and not line.text.endswith(".")
        )
    }
    starts = _columns([line for line in lines if id(line) in headings]) or [0.0]
    columns: dict[int, list[Line]] = {}
    for line in lines:
        columns.setdefault(_column_of(line.x0, starts), []).append(line)

    found: list[EditableLine] = []
    for index, line in enumerate(lines):
        if index in bullets:
            continue
        text = plain[index]
        match = _BULLET.match(text)
        start = (
            match.end() if match and text[match.end() :].strip() else len(text) - len(text.lstrip())
        )
        end = len(text.rstrip())

        column = columns[_column_of(line.x0, starts)]
        left, right = min(other.x0 for other in column), max(other.x1 for other in column)
        beside = [
            other
            for other in lines
            if other is not line and abs(other.baseline - line.baseline) < 1.0
        ]
        bullet = next(
            (
                lines[other]
                for other in bullets
                if abs(lines[other].baseline - line.baseline) < 1.0
                and 0 <= line.x0 - lines[other].x1 < 30
            ),
            None,
        )
        right_limit = min(
            [right] + [other.x0 - _GAP_TO_NEIGHBOUR for other in beside if other.x0 >= line.x1 - 1]
        )
        left_limit = max(
            [left] + [other.x1 + _GAP_TO_NEIGHBOUR for other in beside if other.x1 <= line.x0 + 1]
        )
        if bullet is not None:
            left_limit = line.x0
        found.append(
            EditableLine(
                id=f"{number}-{index}",
                page=number,
                line=line,
                prefix=text[:start].strip() if match else "",
                text=text[start:end],
                start=start,
                heading=id(line) in headings,
                bullet=bullet,
                marks=_marks_beside(line, drawings) if bullet is None and not match else (),
                links=tuple(line_links.get(index, [])),
                left_limit=left_limit,
                right_limit=right_limit,
                right_aligned=line.x1 >= right - 2 and line.x0 > left + (right - left) * 0.35,
                leading=_leading(line, column),
            )
        )
    return found, starts


def read_layout(doc: pymupdf.Document) -> Layout:
    """Every line of the resume, grouped under the heading it sits beneath."""
    sections: list[Section] = []
    multi_column: set[int] = set()
    for number in range(doc.page_count):
        found, starts = _read_page(doc, number)
        if len(starts) > 1:
            multi_column.add(number)
        # Each column's sections on this page, as (heading's baseline, section).
        open_sections: dict[int, list[tuple[float, Section]]] = {}
        page_sections: list[tuple[int, float, Section]] = []
        for item in found:
            if not item.heading:
                continue
            section = Section(title=item.text.rstrip(":").strip() or item.text, lines=[item])
            column = _column_of(item.line.x0, starts)
            open_sections.setdefault(column, []).append((item.line.baseline, section))
            page_sections.append((column, item.line.baseline, section))

        # Lines above every heading continue the last section of the page before;
        # on the first page they are the name and contact details.
        carried = sections[-1] if sections else Section(title="Header")
        for item in found:
            if item.heading:
                continue
            candidates = [
                section
                for baseline, section in open_sections.get(_column_of(item.line.x0, starts), [])
                if baseline < item.line.baseline
            ]
            (candidates[-1] if candidates else carried).lines.append(item)

        if carried.lines and (not sections or carried is not sections[-1]):
            sections.append(carried)
        sections += [section for _, _, section in sorted(page_sections, key=lambda s: s[:2])]

    for section in sections:
        section.lines.sort(key=lambda item: (item.page, round(item.line.baseline), item.line.x0))
    width_height = [(doc[n].rect.width, doc[n].rect.height) for n in range(doc.page_count)]
    return Layout(pages=width_height, sections=sections, multi_column=multi_column)


def _find_current(page: pymupdf.Page, original: Line) -> Line | None:
    """The line as it stands now, after earlier edits rewrote others on the page."""
    wanted = raw_text(original)
    return next(
        (
            line
            for line in read_lines(page)
            if abs(line.baseline - original.baseline) < 0.5 and raw_text(line) == wanted
        ),
        None,
    )


def _change(doc: pymupdf.Document, item: EditableLine, new: str, uris: dict[str, str]) -> bool:
    """Rewords the line, touching only the characters that differ."""
    old = item.text
    same_start = 0
    while same_start < min(len(old), len(new)) and old[same_start] == new[same_start]:
        same_start += 1
    same_end = 0
    while (
        same_end < min(len(old), len(new)) - same_start
        and old[len(old) - 1 - same_end] == new[len(new) - 1 - same_end]
    ):
        same_end += 1

    page = doc[item.page]
    line = _find_current(page, item.line)
    if line is None:
        raise _Refused("unsafe")
    start, end = item.start + same_start, item.start + len(old) - same_end
    inserted = new[same_start : len(new) - same_end]
    # New words need one style to be written in. Words only taken out need none,
    # so a deletion may run across styles: each style's part is taken out in turn.
    pieces = [(start, end, inserted)] if inserted else _per_span(line, start, end)
    exact = True
    for piece_start, piece_end, words in pieces:
        try:
            exact = (
                replace_in_line(
                    doc,
                    page,
                    line,
                    piece_start,
                    piece_end,
                    words,
                    left_limit=item.left_limit,
                    right_limit=item.right_limit,
                    right_aligned=item.right_aligned,
                )
                and exact
            )
        except CannotReplaceError as exc:
            # Within one line "not found" means the change runs across two styles.
            raise _Refused("mixed_style" if exc.reason == "not_found" else exc.reason) from exc
        expected = _same(raw_text(line)[:piece_start] + words + raw_text(line)[piece_end:])
        found = next(
            (
                other
                for other in read_lines(page)
                if abs(other.baseline - item.line.baseline) < 0.5
                and _same(raw_text(other)) == expected
            ),
            None,
        )
        if found is None:
            raise _Refused("unsafe")
        line = found
    if item.links:
        # The page keeps its own list of links until it is loaded again.
        page = doc.reload_page(page)
        _follow_links(doc, page, item, start, end, inserted, uris)
    return exact


_WORD_BREAK = " |,;·•"


def _same(text: str) -> str:
    """Text as it reads, whatever spaces and hyphens the file stores: written
    text can read back with no-break spaces, and a resume's own font can turn a
    hyphen into a soft one."""
    return text.replace("\xa0", " ").replace("\xad", "-")


def _per_span(line: Line, start: int, end: int) -> list[tuple[int, int, str]]:
    """Characters `start` to `end`, split where the line's spans meet, last first
    (so taking one part out does not move the parts still to come)."""
    parts: list[tuple[int, int, str]] = []
    offset = 0
    for span in line.spans:
        a, b = max(start, offset), min(end, offset + len(span.text))
        if a < b:
            parts.append((a, b, ""))
        offset += len(span.text)
    return list(reversed(parts))


def _follow_links(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    item: EditableLine,
    start: int,
    end: int,
    inserted: str,
    uris: dict[str, str],
) -> None:
    """Moves the line's links onto their words after characters `start` to `end`
    became `inserted`, and rewrites an address that spelled out changed words.
    """
    old_raw = _plain(item.line)
    new_raw = old_raw[:start] + inserted + old_raw[end:]
    delta = len(inserted) - (end - start)
    line = next(
        (
            other
            for other in read_lines(page)
            if abs(other.baseline - item.line.baseline) < 0.5
            and other.x0 < item.line.x1 + 5
            and item.line.x0 < other.x1 + 5
            and _same(_plain(other)) == _same(new_raw)
        ),
        None,
    )
    if line is None:
        return
    for link in item.links:
        if link.end <= start:
            a, b = link.start, link.end
        elif link.start >= end:
            a, b = link.start + delta, link.end + delta
        elif start <= link.start and link.end <= end:
            # All of the linked words were replaced: the link covers what replaced them.
            a, b = start, start + len(inserted)
            while a < b and new_raw[a] in _WORD_BREAK:
                a += 1
            while b > a and new_raw[b - 1] in _WORD_BREAK:
                b -= 1
        else:
            # The change touches the linked words: the link covers the word(s) there now.
            a, b = min(link.start, start), max(link.end, end) + delta
            while a > 0 and new_raw[a - 1] not in _WORD_BREAK:
                a -= 1
            while b < len(new_raw) and new_raw[b] not in _WORD_BREAK:
                b += 1
        words = new_raw[a:b].strip()
        if not words:
            links.remove(page, link.rect)
            continue
        a = new_raw.index(words, a)
        uri = uris.get(link.id) or link.uri
        rect = (
            _x_at(doc, page, line, a),
            link.rect[1],
            _x_at(doc, page, line, a + len(words)),
            link.rect[3],
        )
        links.move(page, link.rect, rect, links.follow_words(uri, link.text, words))


def _texts(page: pymupdf.Page) -> list[str]:
    return sorted(line.text for line in read_lines(page))


def _remove(page: pymupdf.Page, item: EditableLine) -> None:
    gone = [item.line] + ([item.bullet] if item.bullet else [])
    expected = _texts(page)
    for line in gone:
        expected.remove(line.text)
    for line in gone:
        for span in line.spans:
            if span.text.strip():
                # Hugging the letters, so a tall line above or below is not caught.
                page.add_redact_annot(
                    pymupdf.Rect(
                        span.x0,
                        span.baseline - span.size * 0.7,
                        span.x1,
                        span.baseline + span.size * 0.15,
                    ),
                    fill=None,
                )
    for shape in item.marks:
        page.add_redact_annot(shape["rect"] + (-0.5, -0.5, 0.5, 0.5), fill=None)
    links = page.get_links()
    # Line art wholly inside those boxes (a drawn bullet, a link's underline) goes too.
    page.apply_redactions(images=0, graphics=1, text=0)
    band = pymupdf.Rect(item.line.x0, item.line.y0, item.line.x1, item.line.y1)
    kept = {(round(link["from"].x0), round(link["from"].y0)) for link in page.get_links()}
    for link in links:
        area = link["from"]
        inside = band.contains(pymupdf.Point((area.x0 + area.x1) / 2, (area.y0 + area.y1) / 2))
        if not inside and (round(area.x0), round(area.y0)) not in kept:
            # A link put back is a new one: its old identity would clash.
            link.pop("xref", None)
            link.pop("id", None)
            page.insert_link(link)
    if _texts(page) != expected:
        raise CannotShiftError("Removing the line disturbed the text around it.")


def _style_span(item: EditableLine) -> Span:
    """The span a new line under this one is written in: the one holding most of its words."""
    offset, best, most = 0, item.line.last_span, -1
    for span in item.line.spans:
        inside = max(
            0, min(offset + len(span.text), item.start + len(item.text)) - max(offset, item.start)
        )
        if span.text.strip() and inside > most:
            best, most = span, inside
        offset += len(span.text)
    return best


def _x_at(doc: pymupdf.Document, page: pymupdf.Page, line: Line, position: int) -> float:
    """Where character `position` of the line (see `raw_text`) is drawn."""
    offset = 0
    for span in line.spans:
        if position <= offset + len(span.text):
            font = font_for(doc, page, span, span.text)
            before = span.text[: position - offset]
            if font is None:
                share = len(before) / max(1, len(span.text))
                return span.x0 + (span.x1 - span.x0) * share
            return span.x0 + font.width(before)
        offset += len(span.text)
    return line.x1


def _wrap(text: str, font: LineFont, width: float) -> list[str] | None:
    """Breaks `text` into lines no wider than `width`, or None if a word alone is wider."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}" if current else word
        if font.width(trial) <= width:
            current = trial
            continue
        if not current or font.width(word) > width:
            return None
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


@dataclass
class _Addition:
    index: int
    # The line it goes under, and the line whose look it copies.
    item: EditableLine
    style: EditableLine
    font: LineFont
    text_x: float
    lines: list[str]
    # A one-line addition copying a line of several styles ("Name | Tech"):
    # each piece of the new text in the style of the matching piece.
    pieces: list[tuple[str, LineFont]] | None = None

    @property
    def leading(self) -> float:
        return self.style.leading


def _plan_addition(
    doc: pymupdf.Document, index: int, item: EditableLine, style: EditableLine, text: str
) -> _Addition | Reason:
    page = doc[item.page]
    span = _style_span(style)
    font = font_for(doc, page, span, text)
    if font is None:
        return "no_font"
    text_x = _x_at(doc, page, style.line, style.start) if style.prefix else style.line.x0
    # A copied line may be held short by text beside it (a date); the new one is not.
    right = max(item.right_limit, style.right_limit)
    pieces = _styled_pieces(doc, page, style, text)
    if pieces is not None and text_x + sum(f.width(t) for t, f in pieces) <= right:
        return _Addition(
            index=index,
            item=item,
            style=style,
            font=font,
            text_x=text_x,
            lines=[text],
            pieces=pieces,
        )
    lines = _wrap(text, font, right - text_x)
    if not lines:
        return "no_room"
    return _Addition(index=index, item=item, style=style, font=font, text_x=text_x, lines=lines)


_DELIMITER = re.compile(r"^[\s|:,;·•—–\-/()]+")


def _styled_pieces(
    doc: pymupdf.Document, page: pymupdf.Page, style: EditableLine, text: str
) -> list[tuple[str, LineFont]] | None:
    """Splits `text` the way the style line is split into styles, or None.

    "Gitlytics | Python, Flask" is a bold name, a plain " | " and an italic
    list. A new "Rolesetu | Next.js, FastAPI" is written the same way: the
    words before the " | " bold, the rest italic. Only done when every
    separator of the style line is found in the new text.
    """
    spans: list[Span] = []
    offset = 0
    for span in style.line.spans:
        start = max(0, style.start - offset)
        if span.text[start:].strip():
            spans.append(span if start == 0 else replace(span, text=span.text[start:]))
        offset += len(span.text)
    if len({(span.font, round(span.size, 1), span.color) for span in spans}) < 2:
        return None

    # Each span becomes "separator, then words": the separator part is matched
    # literally in the new text, the words part takes whatever comes before the next.
    parts: list[tuple[str, Span]] = []
    for number, span in enumerate(spans):
        found = _DELIMITER.match(span.text) if number else None
        if found:
            parts.append((found.group(0), span))
        words = span.text[found.end() :] if found else span.text
        if words.strip():
            parts.append(("", span))
    last_words = max(number for number, (delimiter, _) in enumerate(parts) if not delimiter)
    pattern = "".join(
        re.escape(delimiter) if delimiter else "(.+)" if number == last_words else "(.+?)"
        for number, (delimiter, _) in enumerate(parts)
    )
    match = re.fullmatch(pattern, text)
    if match is None:
        return None
    groups = iter(match.groups())
    pieces: list[tuple[str, LineFont]] = []
    for delimiter, span in parts:
        piece = delimiter or next(groups)
        font = font_for(doc, page, span, piece)
        if font is None:
            return None
        pieces.append((piece, font))
    return pieces


def _copy_shape(page: pymupdf.Page, drawing: Drawing, down: float) -> None:
    """Draws the shape again, `down` points lower, with the same fill and outline."""
    shape = page.new_shape()
    move = pymupdf.Point(0, down)
    for kind, *points in drawing["items"]:
        if kind == "l":
            shape.draw_line(points[0] + move, points[1] + move)
        elif kind == "c":
            shape.draw_bezier(*(point + move for point in points))
        elif kind == "re":
            shape.draw_rect(points[0] + (0, down, 0, down))
        elif kind == "qu":
            shape.draw_quad(points[0] * pymupdf.Matrix(1, 0, 0, 1, 0, down))
    shape.finish(
        fill=drawing.get("fill"),
        color=drawing.get("color"),
        width=drawing.get("width") or 0,
        closePath=bool(drawing.get("closePath")),
        even_odd=bool(drawing.get("even_odd")),
        fill_opacity=drawing.get("fill_opacity") or 1,
        stroke_opacity=drawing.get("stroke_opacity") or 1,
    )
    shape.commit()


def _write_addition(doc: pymupdf.Document, page: pymupdf.Page, addition: _Addition) -> None:
    item, style = addition.item, addition.style
    baseline = item.line.baseline + addition.leading
    for shape in style.marks:
        _copy_shape(page, shape, baseline - style.line.baseline)
    if style.bullet is not None:
        mark = style.bullet.spans[0]
        mark_font = font_for(doc, page, mark, mark.text.strip())
        if mark_font is not None:
            mark_font.write(page, style.bullet.x0, baseline, style.bullet.text)
    elif style.prefix:
        position = _plain(style.line).index(style.prefix)
        mark = style.line.spans[0]
        mark_font = font_for(doc, page, mark, style.prefix)
        if mark_font is not None:
            mark_font.write(page, _x_at(doc, page, style.line, position), baseline, style.prefix)
    if addition.pieces is not None:
        x = addition.text_x
        starts: list[tuple[int, float, LineFont]] = []
        offset = 0
        for piece, font in addition.pieces:
            font.write(page, x, baseline, piece)
            starts.append((offset, x, font))
            offset += len(piece)
            x += font.width(piece)
        text = "".join(piece for piece, _ in addition.pieces)

        def x_of(position: int) -> float:
            begin, left, font = next(entry for entry in reversed(starts) if entry[0] <= position)
            return left + font.width(text[begin:position])

        links.add_for_words(page, text, x_of, baseline, addition.font.size)
        return
    for number, words in enumerate(addition.lines):
        line_baseline = baseline + number * style.leading
        addition.font.write(page, addition.text_x, line_baseline, words)
        links.add_for_words(
            page,
            words,
            lambda position, words=words: addition.text_x + addition.font.width(words[:position]),
            line_baseline,
            addition.font.size,
        )


def _apply(
    pdf: bytes, edits: list[Edit], skip: dict[int, Reason], new_uris: dict[str, str]
) -> tuple[bytes, dict[int, Outcome]]:
    outcomes: dict[int, Outcome] = {index: Outcome(False, reason) for index, reason in skip.items()}
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        layout = read_layout(doc)
        lines = layout.by_id()

        # The last word on each line wins; removing a line wins over rewording it.
        removals: dict[str, int] = {}
        changes: dict[str, tuple[int, str]] = {}
        additions: list[tuple[int, EditableLine, EditableLine, str]] = []
        for index, edit in enumerate(edits):
            if index in skip:
                continue
            target = lines.get(edit.after_id if isinstance(edit, AddLine) else edit.line_id)
            if target is None:
                outcomes[index] = Outcome(False, "not_found")
            elif isinstance(edit, RemoveLine) or (
                isinstance(edit, ChangeText) and not edit.text.strip()
            ):
                removals[target.id] = index
            elif isinstance(edit, ChangeText):
                if edit.text.strip() == target.text.strip():
                    outcomes[index] = Outcome(True)
                else:
                    changes[target.id] = (index, edit.text.strip())
            elif target.page in layout.multi_column:
                outcomes[index] = Outcome(False, "two_columns")
            else:
                # Fonts belong to a page, so the look is copied only from the same page.
                style = lines.get(edit.style_id or "") or target
                if style.page != target.page:
                    style = target
                additions.append((index, target, style, " ".join(edit.text.split())))
        for line_id, (index, _text) in list(changes.items()):
            if line_id in removals:
                outcomes[index] = Outcome(True)
                del changes[line_id]

        # 0. Addresses the user typed for links, while every link is where the file has it.
        for item in lines.values():
            for link in item.links:
                uri = new_uris.get(link.id)
                if uri and uri != link.uri:
                    links.set_uri(doc[item.page], link.rect, uri)

        # 1. Words, which never move anything.
        for line_id, (index, text) in changes.items():
            try:
                exact = _change(doc, lines[line_id], text, new_uris)
            except _Refused as exc:
                outcomes[index] = Outcome(False, exc.reason)
                continue
            outcomes[index] = Outcome(True, exact_font=exact)

        # 2. Lines removed and added, bottom of each page first, so every edit
        # still finds its line where the original file has it.
        planned: list[_Addition] = []
        for index, item, style, text in additions:
            plan = _plan_addition(doc, index, item, style, text)
            if isinstance(plan, _Addition):
                planned.append(plan)
            else:
                outcomes[index] = Outcome(False, plan)

        for number in range(doc.page_count):
            page = doc[number]
            removed_here = [lines[line_id] for line_id in removals if lines[line_id].page == number]
            # A gap closes only when nothing is left on that line of the page.
            remaining = [
                item.line.baseline
                for item in lines.values()
                if item.page == number and item.id not in removals
            ]
            closing = {
                item.id
                for item in removed_here
                if number not in layout.multi_column
                and not any(abs(baseline - item.line.baseline) < 1.0 for baseline in remaining)
            }
            # Of several lines removed side by side, one closes the gap.
            seen: set[float] = set()
            for item in sorted(removed_here, key=lambda item: item.line.x0):
                key = round(item.line.baseline, 1)
                if item.id in closing and key in seen:
                    closing.discard(item.id)
                seen.add(key)

            spare = page.rect.height - editor.MIN_BOTTOM_MARGIN - editor.content_bottom(page)
            spare += sum(lines[line_id].leading for line_id in closing)
            adding_here: list[_Addition] = []
            for plan in sorted(
                (plan for plan in planned if plan.item.page == number),
                key=lambda plan: (plan.item.line.baseline, plan.index),
            ):
                needed = len(plan.lines) * plan.leading
                if needed > spare + 0.01:
                    outcomes[plan.index] = Outcome(False, "no_room")
                    continue
                spare -= needed
                adding_here.append(plan)

            # Run from the largest key down. On one line, additions come before
            # removing it, so new lines take the removed one's place; of several
            # additions under one line the last is made first, because each new
            # line goes straight under it and pushes the earlier ones down.
            steps: list[tuple[float, int, int, _Addition | EditableLine]] = [
                (plan.item.line.baseline, 1, plan.index, plan) for plan in adding_here
            ] + [(item.line.baseline, 0, 0, item) for item in removed_here]
            for _baseline, _order, _tie, step in sorted(steps, key=lambda s: s[:3], reverse=True):
                if isinstance(step, _Addition):
                    item = step.item
                    try:
                        editor.move_down(
                            doc,
                            page,
                            [
                                (
                                    item.line.baseline + item.leading * 0.3,
                                    len(step.lines) * step.leading,
                                )
                            ],
                        )
                    except CannotShiftError as exc:
                        raise _Undo(step.index, "unsafe") from exc
                    page = doc.reload_page(page)
                    page.wrap_contents()
                    _write_addition(doc, page, step)
                    outcomes[step.index] = Outcome(True, exact_font=step.font.exact)
                else:
                    index = removals[step.id]
                    try:
                        _remove(page, step)
                        if step.id in closing:
                            editor.move_down(
                                doc,
                                page,
                                [(step.line.baseline + step.leading * 0.3, -step.leading)],
                            )
                            page = doc.reload_page(page)
                    except CannotShiftError as exc:
                        raise _Undo(index, "unsafe") from exc
                    outcomes[index] = Outcome(True)

        if any(outcome.applied and not outcome.exact_font for outcome in outcomes.values()):
            doc.subset_fonts()  # a stand-in font is a whole typeface; keep only the letters used
        data: bytes = doc.tobytes(garbage=3, deflate=True)
    return data, outcomes


def apply_edits(
    pdf: bytes, edits: list[Edit], new_uris: dict[str, str] | None = None
) -> tuple[bytes, list[Outcome]]:
    """Applies the edits in order and returns the new file with what happened
    to each one. An edit that would disturb the text around it is left out
    and reported, and the rest are made without it.

    `new_uris` gives links new addresses, by link id (see `LineLink`).
    """
    skip: dict[int, Reason] = {}
    for _attempt in range(len(edits) + 1):
        try:
            data, outcomes = _apply(pdf, edits, skip, new_uris or {})
        except _Undo as undo:
            skip[undo.index] = undo.reason
            continue
        missing = Outcome(False, "not_found")
        return data, [outcomes.get(index, missing) for index in range(len(edits))]
    raise RuntimeError("Every edit was undone and the file still could not be rebuilt.")


def open_pdf(pdf: bytes) -> pymupdf.Document:
    try:
        return pymupdf.open(stream=pdf, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any failure to open means the same thing here
        raise editor.ResumeEditError("unreadable") from exc
