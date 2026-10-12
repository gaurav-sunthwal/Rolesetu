"""Chooses the font new text is written in, so it matches the text beside it.

Three cases, best first:
 1. The resume uses a standard PDF font (Helvetica, Times, Courier) that is not
    stored in the file. The same standard font is used: an exact match.
 2. The resume carries its own font. It is reused when it contains every
    letter needed. (A PDF usually stores only the letters it already uses.)
 3. A letter is missing. A full copy of the same typeface is looked up on this
    machine; failing that, an open typeface drawn to the same widths, shipped
    in `backend/assets/fonts`, is used.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pymupdf

from backend.core.config import get_settings
from backend.modules.tailoring.pdf.section import Span

_STANDARD = {
    "helvetica": "helv",
    "helvetica-bold": "hebo",
    "helvetica-oblique": "heit",
    "helvetica-boldoblique": "hebi",
    "times-roman": "tiro",
    "times-bold": "tibo",
    "times-italic": "tiit",
    "times-bolditalic": "tibi",
    "courier": "cour",
    "courier-bold": "cobo",
    "courier-oblique": "coit",
    "courier-boldoblique": "cobi",
}

# Typeface -> file names to look for, the real one first, then open stand-ins
# drawn to the same letter widths (Liberation, Carlito, Caladea, Gelasio, DejaVu).
# "{}" is replaced by the style: "", " Bold", " Italic", " Bold Italic" and
# "-Regular", "-Bold", "-Italic", "-BoldItalic".
_FAMILIES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (
        re.compile(r"arial|helvetica|liberation ?sans", re.I),
        ("Arial{}.ttf", "LiberationSans-{}.ttf"),
    ),
    (
        re.compile(r"times|liberation ?serif", re.I),
        ("Times New Roman{}.ttf", "LiberationSerif-{}.ttf"),
    ),
    (re.compile(r"calibri|carlito", re.I), ("Calibri{}.ttf", "Carlito-{}.ttf")),
    (re.compile(r"cambria|caladea", re.I), ("Cambria{}.ttf", "Caladea-{}.ttf")),
    (re.compile(r"georgia|gelasio", re.I), ("Georgia{}.ttf", "Gelasio-{}.ttf")),
    (re.compile(r"verdana|dejavu ?sans", re.I), ("Verdana{}.ttf", "DejaVuSans{}.ttf")),
    (re.compile(r"courier|liberation ?mono", re.I), ("Courier New{}.ttf", "LiberationMono-{}.ttf")),
]
# Shipped with the backend, so a server with no fonts installed still has these.
_BUNDLED_FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
_SYSTEM_FONT_DIRS = (
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
)


@dataclass
class LineFont:
    """Something that can measure and write text in one style."""

    size: float
    color: tuple[float, float, float]
    # One of the two is set: a standard PDF font's short name, or a loaded font.
    standard: str = ""
    font: pymupdf.Font | None = None
    exact: bool = True

    def can_write(self, text: str) -> bool:
        if self.font is not None:
            return all(self.font.has_glyph(ord(char)) for char in text)
        try:
            text.encode("latin-1")
        except UnicodeEncodeError:
            return False
        return True

    def width(self, text: str) -> float:
        if self.font is not None:
            return float(self.font.text_length(text, fontsize=self.size))
        return float(pymupdf.get_text_length(text, fontname=self.standard, fontsize=self.size))

    def write(self, page: pymupdf.Page, x: float, baseline: float, text: str) -> None:
        if self.font is not None:
            writer = pymupdf.TextWriter(page.rect, color=self.color)
            writer.append((x, baseline), text, font=self.font, fontsize=self.size)
            writer.write_text(page)
        else:
            page.insert_text(
                (x, baseline), text, fontname=self.standard, fontsize=self.size, color=self.color
            )


@lru_cache(maxsize=1)
def _font_files() -> dict[str, Path]:
    """Every font file on this machine, by lower-cased file name."""
    # Earlier folders win: a real copy of a font on this machine is preferred
    # to the look-alike shipped with the backend.
    folders = [get_settings().font_dir, *_SYSTEM_FONT_DIRS, str(_BUNDLED_FONT_DIR)]
    found: dict[str, Path] = {}
    for folder in folders:
        if not folder or not Path(folder).is_dir():
            continue
        for path in Path(folder).rglob("*.[to]tf"):
            found.setdefault(path.name.lower(), path)
    return found


def _stand_in(name: str) -> pymupdf.Font | None:
    bold = bool(re.search(r"bold|black|heavy|semibold", name, re.I))
    italic = bool(re.search(r"italic|oblique", name, re.I))
    spaced = (" Bold" if bold else "") + (" Italic" if italic else "")
    dashed = ("Bold" if bold else "") + ("Italic" if italic else "") or "Regular"
    files = _font_files()
    for family, patterns in _FAMILIES:
        if not family.search(name):
            continue
        for pattern in patterns:
            for style in (spaced, dashed, f"-{dashed}" if dashed != "Regular" else ""):
                path = files.get(pattern.format(style).lower())
                if path is not None:
                    return pymupdf.Font(fontfile=str(path))
    return None


def _color(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)


def font_for(doc: pymupdf.Document, page: pymupdf.Page, span: Span, text: str) -> LineFont | None:
    """A font that can write `text` in the style of `span`, or None when there is none."""
    color = _color(span.color)
    entry = next(
        (font for font in page.get_fonts(full=True) if font[3].split("+")[-1] == span.font), None
    )
    embedded = entry is not None and entry[1] != "n/a"

    if not embedded:
        standard = _STANDARD.get(span.font.lower())
        if standard:
            exact = LineFont(size=span.size, color=color, standard=standard)
            if exact.can_write(text):
                return exact
    elif entry is not None:
        buffer = doc.extract_font(entry[0])[3]
        try:
            own = LineFont(size=span.size, color=color, font=pymupdf.Font(fontbuffer=buffer))
        except Exception:  # noqa: BLE001 - a font the library cannot load is simply not reusable
            own = None
        if own is not None and own.can_write(text):
            return own

    other = _stand_in(span.font)
    if other is None:
        return None
    stand_in = LineFont(size=span.size, color=color, font=other, exact=False)
    return stand_in if stand_in.can_write(text) else None
