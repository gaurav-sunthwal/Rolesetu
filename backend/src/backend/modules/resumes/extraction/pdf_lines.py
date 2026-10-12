"""Reads a PDF into ordered `Line`s using pdfplumber.

Two things make this more than "extract the text":
- Columns. Many resumes have a sidebar. Reading straight across would
  interleave the two columns, so a page with a clear vertical gutter is read
  one column at a time.
- Style. Font size and bold are kept on every line, because headings and entry
  titles are usually distinguished by style, not by wording.
"""

import io
import re
from collections import Counter
from typing import Any

import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError

from backend.modules.resumes.extraction.lines import GAP, Line

MAX_PAGES = 8
_BOLD_HINTS = ("bold", "black", "heavy", "semibold", "demi")
_MIN_GUTTER_WIDTH = 12.0
Word = dict[str, Any]
_UNMAPPED_GLYPH = re.compile(r"\(cid:\d+\)")


class UnreadablePdfError(Exception):
    """The file could not be opened as a PDF."""


def _is_bold(fontname: str) -> bool:
    name = fontname.lower()
    return any(hint in name for hint in _BOLD_HINTS)


def _rows(words: list[Word]) -> list[list[Word]]:
    """Groups words that share a baseline, top to bottom."""
    rows: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        middle = (word["top"] + word["bottom"]) / 2
        if rows:
            last = rows[-1]
            last_middle = sum((w["top"] + w["bottom"]) / 2 for w in last) / len(last)
            if abs(middle - last_middle) <= max(2.0, 0.45 * float(word["size"])):
                last.append(word)
                continue
        rows.append([word])
    return [sorted(row, key=lambda w: w["x0"]) for row in rows]


def _find_gutter(rows: list[list[Word]], width: float) -> float | None:
    """The x position of a column gap, or None for a single-column page.

    A gutter is a vertical band near the middle that almost no row writes
    across, with text on both sides of it for a good share of the page.
    """
    if len(rows) < 12:
        return None
    bins = int(width) + 1
    crossed = [0] * bins
    for row in rows:
        covered: set[int] = set()
        for index, word in enumerate(row):
            end = word["x1"]
            # Normal word spacing counts as covered; a big jump does not.
            if index + 1 < len(row) and row[index + 1]["x0"] - end < 1.5 * float(word["size"]):
                end = row[index + 1]["x0"]
            covered.update(range(int(word["x0"]), min(bins, int(end) + 1)))
        for position in covered:
            crossed[position] += 1

    allowed = max(1, int(0.08 * len(rows)))
    best: tuple[float, float] | None = None
    start: int | None = None
    for position in range(int(width * 0.2), int(width * 0.8) + 1):
        clear = crossed[position] <= allowed
        if clear and start is None:
            start = position
        if (not clear or position == int(width * 0.8)) and start is not None:
            if position - start >= _MIN_GUTTER_WIDTH and (
                best is None or position - start > best[1] - best[0]
            ):
                best = (float(start), float(position))
            start = None
    if best is None:
        return None

    gutter = (best[0] + best[1]) / 2
    left = sum(1 for row in rows if any(w["x1"] <= gutter for w in row))
    right = sum(1 for row in rows if any(w["x0"] >= gutter for w in row))
    if min(left, right) < 6 or min(left, right) < 0.25 * len(rows):
        return None
    return gutter


def _line_from(words: list[Word], page: int, links: list[dict[str, Any]]) -> Line:
    parts: list[str] = []
    for index, word in enumerate(words):
        if index:
            gap = word["x0"] - words[index - 1]["x1"]
            size = float(word["size"])
            if gap > 1.5 * size:
                parts.append(GAP)
            elif gap > 0.06 * size:
                parts.append(" ")
            # Otherwise the two pieces touch: one word drawn in two sizes
            # (small caps), so they are joined with nothing between them.
        parts.append(word["text"])
    weights: Counter[bool] = Counter()
    sizes: Counter[float] = Counter()
    for word in words:
        weights[bool(word["bold"])] += len(word["text"])
        sizes[round(float(word["size"]), 1)] += len(word["text"])
    top = min(w["top"] for w in words)
    bottom = max(w["bottom"] for w in words)
    x0, x1 = words[0]["x0"], words[-1]["x1"]
    line_links = tuple(
        str(link["uri"])
        for link in links
        if link.get("uri")
        and link["top"] < bottom
        and link["bottom"] > top
        and link["x0"] < x1
        and link["x1"] > x0
    )
    # A glyph with no text mapping (very often the bullet) is extracted as
    # "(cid:127)"; show it as a bullet so the rest of the pipeline sees one.
    text = _UNMAPPED_GLYPH.sub("\u2022", "".join(parts))
    return Line(
        text=text,
        size=sizes.most_common(1)[0][0],
        bold=weights[True] > weights[False],
        lead_bold=bool(words[0]["bold"]),
        page=page,
        x0=float(x0),
        links=line_links,
    )


def _page_lines(page: Any, number: int) -> list[Line]:
    # Words are not split on font changes: small caps are drawn as two sizes
    # of the same letters, and splitting there would break every heading.
    # The gap that separates two words scales with the font, so a large
    # small-caps name is not broken between its capital and the rest.
    words: list[Word] = page.extract_words(x_tolerance_ratio=0.18, y_tolerance=3, return_chars=True)
    if not words:
        return []
    for word in words:
        chars = word.pop("chars")
        word["size"] = max(float(char["size"]) for char in chars)
        bold = sum(1 for char in chars if _is_bold(str(char.get("fontname", ""))))
        word["bold"] = bold * 2 > len(chars)
    links: list[dict[str, Any]] = list(page.hyperlinks)
    rows = _rows(words)
    gutter = _find_gutter(rows, float(page.width))
    if gutter is None:
        return [_line_from(row, number, links) for row in rows]

    # Anything above the first row that sits wholly in the right column is a
    # full-width header (name, contact line) and is read first.
    full_width: list[Line] = []
    left: list[Line] = []
    right: list[Line] = []
    in_columns = False
    for row in rows:
        left_words = [w for w in row if (w["x0"] + w["x1"]) / 2 < gutter]
        right_words = [w for w in row if (w["x0"] + w["x1"]) / 2 >= gutter]
        spans = any(w["x0"] < gutter - 2 and w["x1"] > gutter + 2 for w in row)
        if not in_columns and (spans or not (left_words and right_words)) and not right_words:
            # Still possibly the header, but a left-only row could also be the
            # top of the left column; treat it as column text.
            left.append(_line_from(row, number, links))
            continue
        if not in_columns and spans:
            full_width.append(_line_from(row, number, links))
            continue
        in_columns = True
        if spans:
            left.append(_line_from(row, number, links))
            continue
        if left_words:
            left.append(_line_from(left_words, number, links))
        if right_words:
            right.append(_line_from(right_words, number, links))
    return full_width + left + right


def extract_lines(pdf: bytes) -> list[Line]:
    try:
        with pdfplumber.open(io.BytesIO(pdf)) as document:
            lines: list[Line] = []
            for number, page in enumerate(document.pages[:MAX_PAGES]):
                lines.extend(_page_lines(page, number))
            return lines
    except (PDFSyntaxError, ValueError, KeyError, TypeError) as exc:
        raise UnreadablePdfError(str(exc)) from exc
