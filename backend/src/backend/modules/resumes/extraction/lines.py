"""A resume as an ordered list of text lines, plus the helpers every section
parser shares for bullets and for splitting a header line into its parts.
"""

import re
from dataclasses import dataclass

# Wide gap inside a line (for example a right-aligned date) is kept as a tab.
GAP = "\t"

_BULLET = re.compile(
    r"^\s*(?:[•●○◦▪▫■‣⁃∙·➢➤►▸"
    r"✓✔❖♦★*\-–—]|[-])\s+"
)
_NUMBERED = re.compile(r"^\s*\d{1,2}[.)]\s+")
_SEPARATORS = re.compile(r"\t|\s+[|•·—–]\s+|\s+-\s+|\s+@\s+")


@dataclass(frozen=True)
class Line:
    text: str
    size: float = 10.0
    bold: bool = False
    # True when the line starts in bold, even if the rest is regular weight.
    lead_bold: bool = False
    page: int = 0
    x0: float = 0.0
    links: tuple[str, ...] = ()

    @property
    def flat(self) -> str:
        """The text with wide gaps collapsed to single spaces."""
        return re.sub(r"\s+", " ", self.text).strip()


def is_bullet(line: Line) -> bool:
    return bool(_BULLET.match(line.text) or _NUMBERED.match(line.text))


def strip_bullet(text: str) -> str:
    return _NUMBERED.sub("", _BULLET.sub("", text, count=1), count=1).strip()


def fragments(text: str) -> list[str]:
    """Splits a header such as "Engineer | Acme — Pune" into its pieces."""
    return [part.strip(" ,;:") for part in _SEPARATORS.split(text) if part.strip(" ,;:")]


def looks_like_sentence(text: str) -> bool:
    words = text.split()
    return len(words) > 12 or (len(words) > 6 and text.rstrip().endswith("."))


def join_wrapped(lines: list[Line]) -> str:
    """Rebuilds bullets and paragraphs: a line that only continues the one above
    (wrapped text) is glued back on, so each bullet ends up on a single line.
    """
    out: list[str] = []
    previous: Line | None = None
    for line in lines:
        text = strip_bullet(line.flat)
        if not text:
            continue
        continues = (
            previous is not None
            and out
            and not is_bullet(line)
            and (
                line.x0 > previous.x0 + 3
                or text[0].islower()
                or (is_bullet(previous) and not out[-1].rstrip().endswith((".", ":", ";")))
                or (not is_bullet(previous) and not out[-1].rstrip().endswith((".", ":")))
            )
        )
        if continues:
            joiner = "" if out[-1].endswith("-") and text[0].islower() else " "
            out[-1] = f"{out[-1]}{joiner}{text}"
        else:
            out.append(text)
            previous = line
    return "\n".join(out)
