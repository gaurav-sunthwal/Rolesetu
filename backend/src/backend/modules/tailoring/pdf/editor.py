"""Edits a resume PDF in place: rewords the headline, respells skills the way
a job writes them, and adds skills to the Skills section. Nothing else changes.

New skills continue the last line of the row they belong to, in that line's
own font, size and colour. When a line is full, the skill wraps to a new line
and whatever sits below moves down by exactly one line. If the page has no
room for another line, the skill is reported back as not added: text is never
shrunk or squeezed to make it fit.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

import pymupdf

from backend.modules.tailoring import keywords, placement
from backend.modules.tailoring.pdf.fonts import LineFont, font_for
from backend.modules.tailoring.pdf.replace import CannotReplaceError, raw_text, replace_in_line
from backend.modules.tailoring.pdf.section import (
    Entry,
    Line,
    NoSkillsSectionError,
    SkillsSection,
    UnsupportedLayoutError,
    find_skills_section,
    read_lines,
)
from backend.modules.tailoring.pdf.shift import CannotShiftError, Cut, shift_down

# The least blank space left at the foot of a page, in points (72 per inch).
MIN_BOTTOM_MARGIN = 12.0
PREVIEW_DPI = 110

SkipReason = Literal["already_listed", "no_room", "no_font"]


class ResumeEditError(Exception):
    """The resume cannot be edited in place. `reason` says why, in plain words."""

    def __init__(self, reason: Literal["no_skills_section", "unsupported_layout", "unreadable"]):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Added:
    skill: str
    row: str | None
    exact_font: bool


@dataclass(frozen=True)
class Skipped:
    skill: str
    reason: SkipReason


@dataclass(frozen=True)
class Change:
    """A piece of existing text that was (or could not be) reworded."""

    kind: Literal["headline", "respelled"]
    before: str
    after: str
    applied: bool
    # Why not, when it was not applied.
    reason: Literal["not_found", "no_room", "no_font", "unsafe"] | None = None
    exact_font: bool = True


@dataclass(frozen=True)
class EditResult:
    pdf: bytes
    added: list[Added]
    skipped: list[Skipped]
    changes: list[Change] = field(default_factory=list)


# A piece of text and the font it is written in. Each skill keeps its own, so
# one skill needing a stand-in font does not change how its neighbours are drawn.
_Piece = tuple[str, LineFont]


@dataclass
class _Row:
    """What is being added to one row: pieces continuing its last line, then whole new lines."""

    entry: Entry
    tail: list[_Piece] = field(default_factory=list)
    new_lines: list[list[_Piece]] = field(default_factory=list)
    skills: list[tuple[str, bool]] = field(default_factory=list)

    def fits(self, skill: str, section: SkillsSection, font: LineFont) -> bool:
        line, start = (
            (self.new_lines[-1], self.entry.wrap_x)
            if self.new_lines
            else (self.tail, self.entry.last.last_span.x1)
        )
        used = sum(piece_font.width(text) for text, piece_font in line)
        return start + used + font.width(section.separator + skill) <= section.right_limit

    def add(self, skill: str, section: SkillsSection, font: LineFont, *, on_new_line: bool) -> None:
        self.skills.append((skill, font.exact))
        current = self.new_lines[-1] if self.new_lines else self.tail
        if on_new_line:
            # The line being left ends with the separator, as a wrapped list does.
            current.append((section.separator.rstrip(), font))
            self.new_lines.append([(skill, font)])
        else:
            current.append((section.separator + skill, font))


def _write(page: pymupdf.Page, x: float, baseline: float, pieces: list[_Piece]) -> None:
    for text, font in pieces:
        font.write(page, x, baseline, text)
        x += font.width(text)


def _content_bottom(page: pymupdf.Page) -> float:
    bottoms = [line.y1 for line in read_lines(page)]
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        # A box as tall as the page is a background, not content.
        if rect.height < page.rect.height * 0.6:
            bottoms.append(rect.y1)
    return max(bottoms, default=0.0)


def _move_down(doc: pymupdf.Document, page: pymupdf.Page, cuts: list[tuple[float, float]]) -> None:
    """Moves what is below each (y, distance) down. `y` is measured from the top of the page."""
    if page.rotation != 0:
        raise CannotShiftError("Rotated pages are not supported.")
    to_pdf = ~page.transformation_matrix
    pdf_cuts = [Cut(y=(pymupdf.Point(0, y) * to_pdf).y, distance=distance) for y, distance in cuts]

    images = frozenset(str(image[7]) for image in page.get_images(full=True))
    forms: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for _xref, name, _invoker, box in page.get_xobjects():
        forms[str(name)] = ((box[0], box[1]), (box[2], box[3]))

    xrefs = page.get_contents()
    content = b"\n".join(doc.xref_stream(xref) for xref in xrefs)
    doc.update_stream(xrefs[0], shift_down(content, pdf_cuts, images=images, forms=forms))
    if len(xrefs) > 1:
        page.set_contents(xrefs[0])

    # Links are separate from the drawing, so they are moved to follow it.
    for link in page.get_links():
        area = link["from"]
        distance = sum(amount for y, amount in cuts if area.y0 > y)
        if distance:
            link["from"] = area + (0, distance, 0, distance)
            page.update_link(link)


def _plan(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    section: SkillsSection,
    skills: list[str],
    chosen_rows: dict[str, str],
) -> tuple[list[_Row], list[Skipped]]:
    rows = [_Row(entry=entry) for entry in section.entries]
    section_text = " ".join(entry.text for entry in section.entries)
    spare = page.rect.height - MIN_BOTTOM_MARGIN - _content_bottom(page)
    lines_left = int(spare // section.leading) if section.can_grow else 0
    skipped: list[Skipped] = []

    for skill in skills:
        if placement.already_listed(skill, section_text):
            skipped.append(Skipped(skill, "already_listed"))
            continue
        ranked = placement.rank_rows(skill, [(row.entry.label, row.entry.text) for row in rows])
        fonts: dict[int, LineFont] = {}
        for index, _score in ranked:
            font = font_for(doc, page, rows[index].entry.last.last_span, section.separator + skill)
            if font is not None:
                fonts[index] = font
        if not fonts:
            skipped.append(Skipped(skill, "no_font"))
            continue

        # The row the user asked for wins; otherwise the best match. When
        # nothing ties the skill to any row, it goes where there is most space.
        asked = next(
            (i for i, row in enumerate(rows) if row.entry.label == chosen_rows.get(skill)), None
        )
        usable = [(index, score) for index, score in ranked if index in fonts]
        if asked is not None and asked in fonts:
            best = asked
        elif usable[0][1] > 0:
            best = usable[0][0]
        else:
            best = min(fonts, key=lambda index: rows[index].entry.last.x1)

        if rows[best].fits(skill, section, fonts[best]):
            target, new_line = best, False
        elif lines_left > 0:
            target, new_line = best, True
            lines_left -= 1
        else:
            # The best row is full and the page has no room. Another row the
            # skill also belongs in is better than leaving it out; a row it
            # has nothing to do with is not.
            other = next(
                (
                    index
                    for index, score in usable
                    if score > 0 and rows[index].fits(skill, section, fonts[index])
                ),
                None,
            )
            if other is None:
                skipped.append(Skipped(skill, "no_room"))
                continue
            target, new_line = other, False
        rows[target].add(skill, section, fonts[target], on_new_line=new_line)
    return rows, skipped


def add_skills(
    pdf: bytes, skills: list[str], chosen_rows: dict[str, str] | None = None
) -> EditResult:
    """Adds `skills` to the resume. `chosen_rows` maps a skill to the label of the
    row the user wants it in, overriding the automatic choice.
    """
    chosen_rows = chosen_rows or {}
    with _open(pdf) as doc:
        try:
            section = find_skills_section(doc)
        except NoSkillsSectionError as exc:
            raise ResumeEditError("no_skills_section") from exc
        except UnsupportedLayoutError as exc:
            raise ResumeEditError("unsupported_layout") from exc

        page = doc[section.page_index]
        rows, skipped = _plan(doc, page, section, skills, chosen_rows)
        changed = [row for row in rows if row.skills]

        cuts = [
            # Just under the row's last line: the next line down is the first to move.
            (row.entry.last.baseline + section.leading * 0.3, len(row.new_lines) * section.leading)
            for row in changed
            if row.new_lines
        ]
        if cuts:
            try:
                _move_down(doc, page, cuts)
            except CannotShiftError:
                # Keep what fits on existing lines; report the rest as having no room.
                wrapped = {skill for row in changed if row.new_lines for skill, _ in row.skills}
                kept = [skill for skill in skills if skill not in wrapped]
                skipped_now = [Skipped(skill, "no_room") for skill in skills if skill in wrapped]
                result = add_skills(pdf, kept, chosen_rows) if kept else EditResult(pdf, [], [])
                return EditResult(result.pdf, result.added, result.skipped + skipped_now)
            page = doc.reload_page(page)

        # The page's own instructions can leave the drawing space flipped or
        # scaled; closing them off means ours start from a clean state.
        page.wrap_contents()
        added: list[Added] = []
        for row in changed:
            # Rows above this one that grew have pushed it down.
            pushed = sum(distance for y, distance in cuts if row.entry.last.baseline > y)
            last = row.entry.last
            baseline = last.baseline + pushed
            _write(page, last.last_span.x1, baseline, row.tail)
            for number, pieces in enumerate(row.new_lines, start=1):
                _write(page, row.entry.wrap_x, baseline + number * section.leading, pieces)
            added += [
                Added(skill=skill, row=row.entry.label, exact_font=exact)
                for skill, exact in row.skills
            ]

        if any(not item.exact_font for item in added):
            doc.subset_fonts()  # a stand-in font is a whole typeface; keep only the letters used
        data: bytes = doc.tobytes(garbage=3, deflate=True)
    return EditResult(pdf=data, added=added, skipped=skipped)


def _open(pdf: bytes) -> pymupdf.Document:
    try:
        return pymupdf.open(stream=pdf, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any failure to open means the same thing here
        raise ResumeEditError("unreadable") from exc


def _reword(
    doc: pymupdf.Document, headline: str | None, respell: list[tuple[str, str]]
) -> list[Change]:
    """Rewords the headline and respells skills, one line at a time."""
    changes: list[Change] = []

    def attempt(
        kind: Literal["headline", "respelled"],
        before: str,
        after: str,
        page: pymupdf.Page,
        target: tuple[Line, int, int] | None,
        limits: tuple[float, float],
    ) -> None:
        if target is None:
            changes.append(Change(kind, before, after, applied=False, reason="not_found"))
            return
        line, start, end = target
        try:
            exact = replace_in_line(
                doc, page, line, start, end, after, left_limit=limits[0], right_limit=limits[1]
            )
        except CannotReplaceError as exc:
            changes.append(Change(kind, before, after, applied=False, reason=exc.reason))
            return
        changes.append(Change(kind, before, after, applied=True, exact_font=exact))

    if headline:
        page = doc[0]
        lines = read_lines(page)
        found = keywords.find_headline(lines)
        target = None
        if found is not None:
            start = raw_text(found.line).index(found.role)
            target = (found.line, start, start + len(found.role))
        # The headline may be as wide as the page's text is, and no wider.
        limits = (min(line.x0 for line in lines), max(line.x1 for line in lines))
        attempt("headline", found.role if found else "", headline, page, target, limits)

    for written_as, wanted in respell:
        # Read again each time: an earlier change may have moved this line's words.
        try:
            section = find_skills_section(doc)
        except (NoSkillsSectionError, UnsupportedLayoutError):
            changes.append(
                Change("respelled", written_as, wanted, applied=False, reason="not_found")
            )
            continue
        page = doc[section.page_index]
        target = None
        for line in (line for entry in section.entries for line in entry.lines):
            position = keywords.find_spelling(raw_text(line), written_as, wanted)
            if position is not None:
                target = (line, *position)
                break
        left = target[0].x0 if target else 0.0
        attempt("respelled", written_as, wanted, page, target, (left, section.right_limit))
    return changes


def tailor(
    pdf: bytes,
    *,
    skills: list[str],
    chosen_rows: dict[str, str] | None = None,
    headline: str | None = None,
    respell: list[tuple[str, str]] | None = None,
) -> EditResult:
    """Applies every requested change and returns the new file with a record of
    what was done. Existing text is reworded first, then skills are added, so
    the additions are placed against the lines as they finally stand.
    """
    changes: list[Change] = []
    if headline or respell:
        with _open(pdf) as doc:
            changes = _reword(doc, headline, respell or [])
            if any(change.applied for change in changes):
                if any(change.applied and not change.exact_font for change in changes):
                    doc.subset_fonts()
                pdf = doc.tobytes(garbage=3, deflate=True)
    if not skills:
        return EditResult(pdf=pdf, added=[], skipped=[], changes=changes)
    result = add_skills(pdf, skills, chosen_rows)
    return EditResult(result.pdf, result.added, result.skipped, changes)


def contains_skill(pdf_text: str, skill: str) -> bool:
    """Whether a text reader, such as a job site's, would find the skill in the file."""
    flat = re.sub(r"\s+", " ", pdf_text.replace("\xa0", " "))
    return re.search(rf"(?<![\w+#]){re.escape(skill)}(?![\w+#])", flat, re.IGNORECASE) is not None


def render_pages(pdf: bytes) -> list[bytes]:
    """Each page as a PNG, for the before-and-after preview."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return [page.get_pixmap(dpi=PREVIEW_DPI).tobytes("png") for page in doc]
