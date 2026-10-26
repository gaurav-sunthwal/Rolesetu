"""Keeps a resume's links working while its words change.

A PDF link is a clickable box drawn over some text, holding an address. The
box knows nothing about the text under it, so editing the words can leave a
link pointing at the old address, or covering the wrong words. Here:

- each link is matched to the words it covers, so the editor can show it;
- when those words change, the box is moved and sized to the new words, and
  an address that spelled out the old words ("github.com/karanm") is
  rewritten to spell the new ones; a drawn underline follows the words too;
- addresses typed into new lines ("github.com/me/app", an email) become links.
"""

import re
from dataclasses import dataclass
from typing import Any

import pymupdf

from backend.modules.tailoring.pdf.section import Line

# Addresses as people write them on a resume, with or without "https://".
URL = re.compile(
    r"(?:https?://|www\.)[^\s|,;()<>]+"
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    r"|(?<![@\w.])[a-z0-9-]+(?:\.[a-z0-9-]+)*\."
    r"(?:com|dev|io|in|org|net|app|me|ai|co|xyz|tech|site|page|link)(?:/[^\s|,;()<>]*)?",
    re.IGNORECASE,
)
# A drawn underline: a thin horizontal shape just under the link's words.
_UNDERLINE_HEIGHT = 2.5


@dataclass(frozen=True)
class LineLink:
    id: str
    uri: str
    rect: tuple[float, float, float, float]
    # The words the link covers, and where they are in `raw_text(line)`.
    text: str
    start: int
    end: int


def href_for(text: str) -> str:
    """The address a piece of text means: "github.com/me" -> "https://github.com/me"."""
    text = text.rstrip(".")
    if "@" in text and not text.lower().startswith(("http", "www.")):
        return f"mailto:{text}"
    if text.lower().startswith(("http://", "https://")):
        return text
    return f"https://{text}"


def _plain_address(value: str) -> str:
    value = re.sub(r"^(?:https?://|mailto:)", "", value.strip(), flags=re.IGNORECASE)
    return re.sub(r"^www\.", "", value, flags=re.IGNORECASE).rstrip("/").lower()


def follow_words(uri: str, old_text: str, new_text: str) -> str:
    """The address after the words it sits on changed.

    "https://github.com/karanm" over "github.com/karanm" becomes
    "https://github.com/karan-dev" when the words become "github.com/karan-dev".
    An address that did not spell out its words (a short "GitHub") is kept.
    """
    if _plain_address(uri) == _plain_address(old_text) and URL.fullmatch(new_text.strip()):
        prefix = uri[: len(uri) - len(uri.lstrip())]
        scheme = re.match(r"^(?:https?://(?:www\.)?|mailto:)", uri, flags=re.IGNORECASE)
        bare = _plain_address(new_text) if scheme else new_text.strip()
        return prefix + (scheme.group(0) if scheme else "") + bare
    return uri


def read_links(page: pymupdf.Page, number: int, lines: list[Line]) -> dict[int, list[LineLink]]:
    """Each line's links, keyed by the line's index in `lines`."""
    found: dict[int, list[LineLink]] = {}
    for count, link in enumerate(page.get_links(), start=1):
        if link.get("kind") != pymupdf.LINK_URI or not link.get("uri"):
            continue
        area = link["from"]
        middle = (area.y0 + area.y1) / 2
        index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.y0 - 1 <= middle <= line.y1 + 1
                and line.x0 - 2 < area.x1
                and area.x0 < line.x1 + 2
            ),
            None,
        )
        if index is None:
            continue
        covered = page.get_textbox(area).replace("\xa0", " ").strip()
        raw = "".join(span.text for span in lines[index].spans).replace("\xa0", " ")
        start = raw.find(covered) if covered else -1
        if start < 0:
            continue
        found.setdefault(index, []).append(
            LineLink(
                id=f"{number}-L{count}",
                uri=str(link["uri"]),
                rect=(area.x0, area.y0, area.x1, area.y1),
                text=covered,
                start=start,
                end=start + len(covered),
            )
        )
    return found


def _same_link(link: dict[str, Any], rect: tuple[float, float, float, float]) -> bool:
    area: pymupdf.Rect = link["from"]
    return bool(abs(area.x0 - rect[0]) < 1.5 and abs(area.y0 - rect[1]) < 1.5)


def find(page: pymupdf.Page, rect: tuple[float, float, float, float]) -> dict[str, Any] | None:
    return next((link for link in page.get_links() if _same_link(link, rect)), None)


def set_uri(page: pymupdf.Page, rect: tuple[float, float, float, float], uri: str) -> bool:
    link = find(page, rect)
    if link is None:
        return False
    link["uri"] = uri
    page.update_link(link)
    return True


def _underline(page: pymupdf.Page, rect: tuple[float, float, float, float]) -> Any | None:
    width = rect[2] - rect[0]
    for drawing in page.get_drawings():
        shape = drawing["rect"]
        if (
            shape.height <= _UNDERLINE_HEIGHT
            and rect[3] - 3 <= shape.y0 <= rect[3] + 2
            and min(shape.x1, rect[2]) - max(shape.x0, rect[0]) > width * 0.5
        ):
            return drawing
    return None


def move(
    page: pymupdf.Page,
    old: tuple[float, float, float, float],
    new: tuple[float, float, float, float],
    uri: str,
) -> None:
    """Moves the link from `old` to `new` with its address, and its underline with it."""
    line = _underline(page, old)
    if line is not None:
        shape = line["rect"]
        # Keep the words: only line art wholly inside this thin box goes.
        page.add_redact_annot(shape + (-0.3, -0.3, 0.3, 0.3), fill=None)
        page.apply_redactions(images=0, graphics=1, text=1)
        drawn = page.new_shape()
        drawn.draw_rect(pymupdf.Rect(new[0], shape.y0, new[2], shape.y1))
        drawn.finish(fill=line.get("fill"), color=line.get("color"), width=line.get("width") or 0)
        drawn.commit()
    link = find(page, old)
    if link is None:
        page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(*new), "uri": uri})
        return
    link["from"] = pymupdf.Rect(*new)
    link["uri"] = uri
    page.update_link(link)


def remove(page: pymupdf.Page, rect: tuple[float, float, float, float]) -> None:
    link = find(page, rect)
    if link is not None:
        page.delete_link(link)


def add_for_words(page: pymupdf.Page, text: str, x_of: Any, baseline: float, size: float) -> None:
    """Makes every address in `text`, written from `x_of(0)`, a link.

    `x_of(i)` is where character `i` of `text` is drawn.
    """
    for match in URL.finditer(text):
        words = match.group(0).rstrip(".")
        rect = pymupdf.Rect(
            x_of(match.start()),
            baseline - size * 0.8,
            x_of(match.start() + len(words)),
            baseline + size * 0.25,
        )
        page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": href_for(words)})
