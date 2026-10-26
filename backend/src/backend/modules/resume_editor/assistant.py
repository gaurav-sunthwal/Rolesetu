"""The resume assistant's plumbing, around one model call.

1. `build_context` writes out what the model needs: every line of the resume
   (as the user has edited it so far) with its id, the profile, and the chat.
   A resume and a profile are a few thousand words at most, so all of it is
   sent. Retrieving pieces by embedding would only add a way to miss the line
   the user means.
2. The model answers with edits to lines, by id (`ai/resume_assistant.py`).
3. `check_answer` keeps only edits to lines that exist, and flags any skill or
   number in new text that nothing the user wrote or saved supports. Flagged
   edits are shown to the user but not applied unless they choose to.
"""

import re
import time
from collections import deque
from dataclasses import dataclass, field

from backend.ai.resume_assistant import AssistantAnswer
from backend.core.exceptions import RateLimitedError
from backend.modules.matches.local.catalog import find_skills
from backend.modules.profiles.schemas import ProfileRead
from backend.modules.resume_editor import pdf as engine
from backend.modules.resume_editor.links import URL, href_for
from backend.modules.resume_editor.schemas import AssistEdit, AssistRequest

# A soft guard on cost, counted per server process. A second instance lets
# a busy user through twice as often; the keys' own quotas are the hard limit.
MAX_MESSAGES = 30
WINDOW_SECONDS = 600.0
_recent: dict[str, deque[float]] = {}

MAX_EDITS = 25
_ADDRESS = re.compile(r"^(?:https?://\S+|mailto:\S+|tel:\S+)$")
_NUMBER = re.compile(r"(?<![\w.])\d[\d,.]*[%+xkKmM]?")


def check_rate(user_key: str) -> None:
    now = time.monotonic()
    sent = _recent.setdefault(user_key, deque())
    while sent and sent[0] < now - WINDOW_SECONDS:
        sent.popleft()
    if len(sent) >= MAX_MESSAGES:
        raise RateLimitedError(
            f"You have sent the assistant {MAX_MESSAGES} messages in the last 10 minutes. "
            "Please wait a few minutes, or keep editing the lines yourself."
        )
    sent.append(now)


@dataclass
class Context:
    """What was shown to the model, kept to check its answer against."""

    prompt: str
    lines: dict[str, engine.EditableLine]
    section_of: dict[str, str]
    # Each line's words as the user sees them now.
    current: dict[str, str]
    # "N1" -> (line it was added under, its key in the editor, its words).
    new_lines: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    removed: set[str] = field(default_factory=set)
    # Link id -> (the line it is on, its address as the user sees it now).
    links: dict[str, tuple[str, str]] = field(default_factory=dict)
    can_add_skills: bool = False
    # Everything the user wrote or saved: what new text may draw on.
    sources: str = ""


def _room(item: engine.EditableLine) -> int | None:
    """Roughly how many characters fit on the line before it overflows."""
    width = item.line.x1 - item.line.x0
    if len(item.text) < 8 or width <= 0:
        return None
    space = (
        item.line.x1 - item.left_limit if item.right_aligned else item.right_limit - item.line.x0
    )
    return max(len(item.text), int(len(item.text) * space / width))


def profile_text(profile: ProfileRead) -> str:
    parts: list[str] = []
    links = [
        f"{name}: {value}"
        for name, value in (
            ("LinkedIn", profile.links.linkedin),
            ("GitHub", profile.links.github),
            ("Portfolio", profile.links.portfolio),
        )
        if value
    ]
    if links:
        parts.append("Links: " + ", ".join(links))
    if profile.full_name or profile.headline:
        parts.append(f"Name: {profile.full_name or ''}. Headline: {profile.headline or ''}")
    if profile.skills:
        parts.append("Skills: " + ", ".join(skill.name for skill in profile.skills))
    for role in profile.experience:
        dates = f"{role.start or '?'} to {role.end or 'present'}"
        parts.append(f"Role: {role.title} at {role.company} ({dates}). {role.description}".strip())
    for project in profile.projects:
        tech = f" Tech: {', '.join(project.tech)}." if project.tech else ""
        link = f" Link: {project.url}." if project.url else ""
        parts.append(f"Project: {project.name}.{tech}{link} {project.description}".strip())
    for school in profile.education:
        years = f" ({school.start_year or '?'} to {school.end_year or '?'})"
        parts.append(f"Education: {school.degree} {school.field or ''}, {school.school}{years}")
    return "\n".join(parts) or "(empty)"


def _notes(item: engine.EditableLine, removed: bool) -> str:
    notes = [
        name
        for name, on in (
            ("heading", item.heading),
            ("bullet", bool(item.prefix or item.bullet or item.marks)),
            ("bold", "bold" in item.line.style[0].lower()),
            ("italic", "italic" in item.line.style[0].lower()),
            ("right-aligned", item.right_aligned),
            ("removed", removed),
        )
        if on
    ]
    room = _room(item)
    if room and not item.heading:
        notes.append(f"max {room} chars")
    return f" [{', '.join(notes)}]" if notes else ""


def build_context(
    layout: engine.Layout,
    skill_rows: list[str] | None,
    request: AssistRequest,
    profile: str,
) -> Context:
    """`skill_rows` is None when skills cannot be added to the resume automatically."""
    drafts = {line.line_id: line for line in request.lines}
    uris = {link.link_id: link.uri for link in request.links}
    lines = layout.by_id()
    context = Context(prompt="", lines=lines, section_of={}, current={})
    context.can_add_skills = skill_rows is not None

    out: list[str] = ["RESUME:"]
    for section in layout.sections:
        out.append(f"## {section.title}")
        for item in section.lines:
            draft = drafts.get(item.id)
            text = draft.text.strip() if draft and draft.text is not None else item.text
            removed = bool(draft and draft.removed)
            context.section_of[item.id] = section.title
            context.current[item.id] = text
            if removed:
                context.removed.add(item.id)
            out.append(f"{item.id}{_notes(item, removed)} {text}")
            for link in item.links:
                uri = uris.get(link.id, link.uri)
                context.links[link.id] = (item.id, uri)
                out.append(f'  {link.id} [link] "{link.text}" opens {uri}')
            for added in draft.added if draft else []:
                ref = f"N{len(context.new_lines) + 1}"
                context.new_lines[ref] = (item.id, added.key, added.text)
                context.section_of[ref] = section.title
                out.append(f"  {ref} [new line under {item.id}] {added.text}")

    if skill_rows is None:
        out.append("\nSKILLS SECTION: skills cannot be added automatically; change its lines.")
    else:
        rows = f" Rows: {', '.join(skill_rows)}." if skill_rows else ""
        out.append(f"\nSKILLS SECTION: skills can be added with add_skill.{rows}")
    if request.skills:
        out.append(f"Skills the user is already adding: {', '.join(request.skills)}")

    out.append(f"\nPROFILE:\n<<<\n{profile}\n>>>")
    if request.history:
        turns = "\n".join(f"{turn.role}: {turn.text}" for turn in request.history)
        out.append(f"\nCONVERSATION:\n<<<\n{turns}\n>>>")
    out.append(f"\nREQUEST:\n{request.message}")
    context.prompt = "\n".join(out)

    said = [turn.text for turn in request.history if turn.role == "user"] + [request.message]
    resume = [item.text for item in lines.values()] + [
        text for _, _, text in context.new_lines.values()
    ]
    context.sources = "\n".join(
        [*said, *resume, *context.current.values(), profile, *uris.values()]
        + [link.uri for item in lines.values() for link in item.links]
    )
    return context


def unsupported(text: str, context: Context, already: str = "") -> list[str]:
    """Skills and numbers in `text` found nowhere in what the user wrote or saved."""
    sources = context.sources.lower()
    known = {mention.skill.name.lower() for mention in find_skills(context.sources)}
    flags: list[str] = []
    for number in _NUMBER.findall(text):
        core = number.rstrip("%+xkKmM.,")
        if (
            core
            and core not in already
            and not re.search(rf"(?<![\d.]){re.escape(core)}(?![\d])", sources)
        ):
            flags.append(number)
    for match in URL.finditer(text):
        address = match.group(0).rstrip(".")
        if address.lower() not in sources and address.lower() not in already.lower():
            flags.append(address)
    for mention in find_skills(text):
        name = mention.skill.name
        written = text[mention.start : mention.end]
        if name.lower() not in known and written.lower() not in sources:
            flags.append(written)
    return list(dict.fromkeys(flags))


def check_answer(answer: AssistantAnswer, context: Context) -> list[AssistEdit]:
    """The model's edits that point at real lines, with unsupported words flagged."""
    edits: list[AssistEdit] = []
    for proposed in answer.edits[:MAX_EDITS]:
        text = " ".join(proposed.text.split())[:400]
        ref = proposed.line.strip()
        style = proposed.style_like.strip() or None
        if style not in context.lines:
            style = None

        if proposed.action == "set_link":
            target = context.links.get(ref)
            # Only something that is an address: never a script or a made-up scheme.
            if text.lower().startswith(("mailto:", "tel:")):
                uri = text
            elif URL.fullmatch(text):
                uri = href_for(text)
            else:
                continue
            if target is None or not _ADDRESS.fullmatch(uri) or uri == target[1]:
                continue
            plain = re.sub(r"^(?:https?://(?:www\.)?|mailto:|tel:)", "", uri).rstrip("/").lower()
            edits.append(
                AssistEdit(
                    kind="set_link",
                    line_id=target[0],
                    new_key=None,
                    style_line_id=None,
                    link_id=ref,
                    text=uri,
                    before=target[1],
                    section=context.section_of.get(target[0]),
                    # An address nobody gave is exactly the kind of thing a model guesses.
                    unsupported=[] if plain in context.sources.lower() else [uri],
                )
            )
            continue

        if proposed.action == "add_skill":
            name = text.strip(" ,.;")
            if not context.can_add_skills or not name or len(name) > 60:
                continue
            edits.append(
                AssistEdit(
                    kind="add_skill",
                    line_id=None,
                    new_key=None,
                    style_line_id=None,
                    text=name,
                    before=None,
                    section=None,
                    unsupported=[] if name.lower() in context.sources.lower() else [name],
                )
            )
            continue

        if ref in context.new_lines:
            anchor, key, words = context.new_lines[ref]
            line_id, new_key, before = anchor, key, words
        elif ref in context.lines and ref not in context.removed:
            line_id, new_key, before = ref, None, context.current[ref]
        else:
            continue  # a line that does not exist, or one the user removed

        if proposed.action in ("change", "add_below") and not text:
            continue
        if proposed.action == "change" and text == before:
            continue
        edits.append(
            AssistEdit(
                kind=proposed.action,
                line_id=line_id,
                new_key=new_key,
                style_line_id=style if proposed.action == "add_below" else None,
                text="" if proposed.action == "remove" else text,
                before=None if proposed.action == "add_below" else before,
                section=context.section_of.get(ref),
                unsupported=(
                    []
                    if proposed.action == "remove"
                    else unsupported(text, context, already=before or "")
                ),
            )
        )
    return edits
