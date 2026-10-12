"""Name, headline, location, phone and links from the top of the resume."""

import re
from urllib.parse import urlparse

from backend.modules.resumes.extraction.keywords import PLACES, has_title_word, is_place
from backend.modules.resumes.extraction.lines import GAP, Line, fragments

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(
    r"(?:https?://|www\.)[^\s|,;()<>]+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|dev|io|in|me|org|net|app|co|ai|tech|xyz|page|site)(?:/[^\s|,;()<>]*)?",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<![\w/])\+?\(?\d[\d\s().-]{7,17}\d(?![\w/])")
_NOT_A_PORTFOLIO = (
    "linkedin.", "github.", "gitlab.", "leetcode.", "hackerrank.", "codechef.", "codeforces.",
    "twitter.", "x.com", "facebook.", "instagram.", "medium.", "stackoverflow.", "kaggle.",
    "youtube.", "google.", "gmail.", "outlook.", "yahoo.", "hotmail.", "t.me", "wa.me",
    "geeksforgeeks.", "behance.", "dribbble.", "credly.", "coursera.", "udemy.",
)  # fmt: skip


def _with_scheme(url: str) -> str:
    url = url.rstrip(".,;:)/")
    return url if re.match(r"^https?://", url, re.IGNORECASE) else f"https://{url}"


def _host(url: str) -> str:
    return urlparse(_with_scheme(url)).netloc.lower().removeprefix("www.")


def links_in(lines: list[Line]) -> list[str]:
    """Every link in these lines: embedded hyperlinks first, then visible URLs."""
    found: list[str] = []
    for line in lines:
        for uri in line.links:
            if uri.lower().startswith(("http://", "https://")):
                found.append(uri)
        without_emails = _EMAIL.sub(" ", line.flat)
        found.extend(match.group(0) for match in _URL.finditer(without_emails))
    unique: dict[str, str] = {}
    for link in found:
        url = _with_scheme(link)
        unique.setdefault(re.sub(r"^https?://(www\.)?", "", url.lower()), url)
    return list(unique.values())


def _phone(text: str) -> str | None:
    for match in _PHONE.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        # Long enough to be a phone number, and not a "2019 - 2023" style range.
        if 10 <= len(digits) <= 13 and not re.fullmatch(r"(19|20)\d{2}\D+(19|20)\d{2}", candidate):
            return candidate
    return None


def _is_plain_words(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z .'’-]*", text))


def _name(header: list[Line]) -> str | None:
    candidates = [
        line
        for line in header[:8]
        if 2 <= len(line.flat.split()) <= 5
        and _is_plain_words(line.flat)
        and not has_title_word(line.flat)
    ]
    if not candidates:
        return None
    # The name is nearly always the largest text at the top of the page.
    best = max(candidates, key=lambda line: line.size)
    name = best.flat
    return name.title() if name.isupper() else name


def _soften_capitals(text: str) -> str:
    """ "REACT NATIVE DEVELOPER | ANDROID & iOS" -> "React Native Developer |
    Android & iOS". Only whole-capital words change; "iOS" and "AWS" are left.
    """
    letters = [char for char in text if char.isalpha()]
    if not letters or sum(1 for char in letters if char.isupper()) / len(letters) < 0.7:
        return text
    return " ".join(
        word.capitalize() if word.isupper() and len(word) > 3 else word for word in text.split(" ")
    )


def _location(pieces: list[str]) -> str | None:
    for piece in pieces:
        if any(char.isdigit() for char in piece) or "@" in piece or len(piece) > 60:
            continue
        words = {word.strip(".,").lower() for word in re.split(r"[\s,]+", piece)}
        if words & PLACES and "," in piece or piece.lower() in PLACES:
            return piece
    return None


def parse_contact(header: list[Line], all_lines: list[Line]) -> dict[str, str | None]:
    name = _name(header)
    text = "\n".join(line.flat for line in header)
    pieces = [piece for line in header for piece in fragments(line.text)]

    def is_headline(text: str) -> bool:
        return (
            text != name
            and has_title_word(text)
            and len(text.split()) <= 8
            and not _EMAIL.search(text)
            and not any(char.isdigit() for char in text)
        )

    headline = next(
        (line.flat for line in header[:8] if is_headline(line.flat)),
        None,
    ) or next((piece for piece in pieces if is_headline(piece)), None)

    # Profile links can sit in a sidebar "Contact" section, so search the
    # whole first page for LinkedIn and GitHub; a portfolio only near the top.
    first_page = [line for line in all_lines if line.page == 0]
    everywhere = links_in(first_page)
    linkedin = next((u for u in everywhere if "linkedin.com/" in u.lower()), None)
    github = next(
        (u for u in everywhere if re.search(r"github\.com/[\w-]+/?$", u, re.IGNORECASE)), None
    )
    portfolio = next(
        (u for u in links_in(header) if not any(skip in _host(u) for skip in _NOT_A_PORTFOLIO)),
        None,
    )

    phone = _phone(text) or _phone("\n".join(line.flat for line in first_page[:25]))
    # In a sidebar layout the place is a line of its own under "Contact".
    location = _location(pieces) or next(
        (line.flat for line in first_page[:14] if GAP not in line.text and is_place(line.flat)),
        None,
    )
    return {
        "full_name": name,
        "headline": _soften_capitals(headline) if headline else None,
        "location": location,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "portfolio": portfolio,
    }
