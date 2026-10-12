"""Changes words inside one line of a PDF, keeping the line's look.

The line is removed and written again in the same fonts, sizes and colours,
with the new words in place of the old. A centred line stays centred. Every
other line on the page is checked afterwards: if anything else changed, the
edit is refused rather than risk damaging the resume.
"""

from dataclasses import dataclass
from typing import Literal

import pymupdf

from backend.modules.tailoring.pdf.fonts import LineFont, font_for
from backend.modules.tailoring.pdf.section import Line, Span, read_lines

# How close a line's middle must be to the page's middle to count as centred.
_CENTRE_TOLERANCE = 3.0

Reason = Literal["not_found", "no_room", "no_font", "unsafe"]


class CannotReplaceError(Exception):
    def __init__(self, reason: Reason):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class _Piece:
    span: Span
    text: str
    font: LineFont
    width: float


def _texts(page: pymupdf.Page) -> list[str]:
    return sorted(line.text for line in read_lines(page))


def _remove(page: pymupdf.Page, line: Line) -> None:
    """Deletes the line's text. Links are put back: removing text drops any link over it."""
    links = page.get_links()
    for span in line.spans:
        if not span.text.strip():
            continue
        # Hugging the letters, so a tall line above or below is not caught.
        area = pymupdf.Rect(
            span.x0, span.baseline - span.size * 0.7, span.x1, span.baseline + span.size * 0.15
        )
        page.add_redact_annot(area, fill=None)
    page.apply_redactions(images=0, graphics=0, text=0)
    kept = {(round(link["from"].x0), round(link["from"].y0)) for link in page.get_links()}
    for link in links:
        if (round(link["from"].x0), round(link["from"].y0)) not in kept:
            link.pop("xref", None)
            page.insert_link(link)


def replace_in_line(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    line: Line,
    start: int,
    end: int,
    new: str,
    *,
    left_limit: float,
    right_limit: float,
) -> bool:
    """Replaces characters `start` to `end` of the line (counted across its
    spans, see `raw_text`) with `new`. Returns whether the page's own font was
    used for the changed words (False means a look-alike was needed).
    """
    index, offset = None, 0
    for number, span in enumerate(line.spans):
        if offset <= start and end <= offset + len(span.text):
            index = number
            break
        offset += len(span.text)
    if index is None:
        # The words run across a change of font or colour: too risky to rebuild.
        raise CannotReplaceError("not_found")
    changed = line.spans[index].text
    changed = changed[: start - offset] + new + changed[end - offset :]

    pieces: list[_Piece] = []
    for number, span in enumerate(line.spans):
        text = changed if number == index else span.text
        font = font_for(doc, page, span, text)
        if font is None:
            raise CannotReplaceError("no_font")
        # An unchanged span keeps the width it had; only the changed one is measured.
        width = font.width(text) if number == index else span.x1 - span.x0
        pieces.append(_Piece(span=span, text=text, font=font, width=width))

    growth = pieces[index].width - (line.spans[index].x1 - line.spans[index].x0)
    centred = abs((line.x0 + line.x1) / 2 - page.rect.width / 2) < _CENTRE_TOLERANCE
    start_shift = -growth / 2 if centred else 0.0
    if (
        line.x0 + start_shift < left_limit - 0.5
        or line.x1 + start_shift + growth > right_limit + 0.5
    ):
        raise CannotReplaceError("no_room")

    others_before = _texts(page)
    others_before.remove(line.text)
    _remove(page, line)
    if _texts(page) != others_before:
        raise CannotReplaceError("unsafe")

    page.wrap_contents()
    for number, piece in enumerate(pieces):
        shift = start_shift + (growth if number > index else 0.0)
        piece.font.write(page, piece.span.x0 + shift, piece.span.baseline, piece.text)
    return pieces[index].font.exact


def raw_text(line: Line) -> str:
    """The line's text exactly as stored, span after span, which is what
    `replace_in_line` counts positions in.
    """
    return "".join(span.text for span in line.spans)
