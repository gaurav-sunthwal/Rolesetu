import asyncio
import base64
import logging
import re
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai import resume_assistant
from backend.core import storage
from backend.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from backend.modules.ai_calls import service as ai_calls
from backend.modules.llm_keys.service import get_decrypted_user_llm_key
from backend.modules.profiles import service as profiles_service
from backend.modules.resume_editor import assistant
from backend.modules.resume_editor import pdf as engine
from backend.modules.resume_editor.schemas import (
    AssistReply,
    AssistRequest,
    EditedResume,
    EditorLine,
    EditorLink,
    EditorPage,
    EditorSection,
    EditOutcome,
    EditRequest,
    LineEdit,
    ResumeLayout,
)
from backend.modules.resumes import repository as resumes_repository
from backend.modules.resumes import service as resumes_service
from backend.modules.resumes.extraction.pdf_lines import extract_lines
from backend.modules.resumes.models import ResumeFile
from backend.modules.resumes.schemas import ResumeRead
from backend.modules.tailoring import service as tailoring_service
from backend.modules.tailoring.pdf import editor
from backend.modules.tailoring.pdf.section import (
    NoSkillsSectionError,
    UnsupportedLayoutError,
    find_skills_section,
)
from backend.modules.tailoring.schemas import AddedSkill, SkillToAdd, SkippedSkill

logger = logging.getLogger(__name__)

_NO_RESUME = "Upload your resume on the Profile page first, then you can edit it here."
_REPLACED = (
    "Your resume was replaced since you opened the editor. Reload the page to edit the new one."
)
_UNREADABLE = "Your stored resume could not be opened. Please upload it again."
_FAILED = (
    "We could not make these changes to your resume. Your resume has not been changed. "
    "Try fewer changes at once; if it keeps failing, this resume's layout is one we cannot "
    "edit yet."
)
_NOT_DONE = {
    "not_found": "This line could not be found any more. Reload the editor and try again.",
    "no_font": (
        "Your resume's font cannot write some of these characters, and no matching font "
        "is available."
    ),
    "unsafe": "Changing this would have disturbed the text around it, so it was left alone.",
    "mixed_style": (
        "This change runs across two styles on the line (for example from bold into plain "
        "text). Change one part at a time."
    ),
    "two_columns": (
        "Lines cannot be added on a page laid out in columns yet, because it would move the "
        "other column too. You can still change or remove lines."
    ),
}
_NO_ROOM = {
    "change": (
        "The new wording is too long for the space on its line. Shorten it, or put the rest "
        "on a new line below."
    ),
    "add_below": "There is no room on this page for another line. Remove or shorten a line first.",
    "remove": _NOT_DONE["unsafe"],
}
_NO_SKILLS_SECTION = (
    "We could not find a Skills section in your resume, or it lists one skill per line, "
    "so skills cannot be added to it automatically. You can still edit its lines."
)
_BOLD = re.compile(r"bold|black|heavy|semibold", re.IGNORECASE)
_ITALIC = re.compile(r"italic|oblique", re.IGNORECASE)


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


async def _latest(db: AsyncSession, user_id: uuid.UUID) -> ResumeFile:
    resume = await resumes_repository.latest(db, user_id)
    if resume is None:
        raise NotFoundError(_NO_RESUME)
    return resume


def _read(pdf: bytes) -> tuple[list[EditorPage], list[EditorSection], list[str]]:
    """Everything that needs the CPU for opening the editor, done in one go."""
    with engine.open_pdf(pdf) as doc:
        layout = engine.read_layout(doc)
        try:
            skills = find_skills_section(doc)
            skills_heading: tuple[int, float] | None = (
                skills.page_index,
                round(skills.heading.baseline, 1),
            )
            rows = [entry.label for entry in skills.entries if entry.label]
        except (NoSkillsSectionError, UnsupportedLayoutError):
            skills_heading, rows = None, []

    images = editor.render_pages(pdf)
    pages = [
        EditorPage(width=width, height=height, image=_encode(image))
        for (width, height), image in zip(layout.pages, images, strict=True)
    ]

    def line_of(item: engine.EditableLine) -> EditorLine:
        font = item.line.style[0]
        box = item.line
        return EditorLine(
            id=item.id,
            text=item.text,
            bullet=bool(item.prefix or item.bullet or item.marks),
            heading=item.heading,
            bold=_BOLD.search(font) is not None,
            italic=_ITALIC.search(font) is not None,
            right_aligned=item.right_aligned,
            can_add_below=item.page not in layout.multi_column,
            page=item.page,
            box=(round(box.x0, 2), round(box.y0, 2), round(box.x1, 2), round(box.y1, 2)),
            links=[EditorLink(id=link.id, text=link.text, uri=link.uri) for link in item.links],
        )

    sections = [
        EditorSection(
            title=section.title,
            is_skills=bool(
                skills_heading
                and section.lines
                and section.lines[0].heading
                and (section.lines[0].page, round(section.lines[0].line.baseline, 1))
                == skills_heading
            ),
            lines=[line_of(item) for item in section.lines],
        )
        for section in layout.sections
    ]
    return pages, sections, rows


async def get_layout(db: AsyncSession, *, user_id: uuid.UUID) -> ResumeLayout:
    resume = await _latest(db, user_id)
    data = await storage.get_file(resume.storage_key)
    try:
        pages, sections, rows = await asyncio.to_thread(_read, data)
    except editor.ResumeEditError as exc:
        raise ValidationFailedError(_UNREADABLE) from exc
    except Exception as exc:
        logger.exception("Reading a resume for the editor failed unexpectedly")
        raise ValidationFailedError(_UNREADABLE) from exc
    return ResumeLayout(
        resume_id=resume.id,
        filename=resume.filename,
        pages=pages,
        sections=sections,
        skill_rows=rows,
    )


def _to_engine(edit: LineEdit) -> engine.Edit:
    if edit.kind == "remove":
        return engine.RemoveLine(edit.line_id)
    if edit.kind == "add_below":
        return engine.AddLine(edit.line_id, edit.text, style_id=edit.style_line_id)
    return engine.ChangeText(edit.line_id, edit.text)


def _message(edit: LineEdit, outcome: engine.Outcome) -> str | None:
    if outcome.applied or outcome.reason is None:
        return None
    if outcome.reason == "no_room":
        return _NO_ROOM[edit.kind]
    return _NOT_DONE[outcome.reason]


@dataclass(frozen=True)
class _Result:
    pdf: bytes
    outcomes: list[EditOutcome]
    added: list[AddedSkill]
    skipped: list[SkippedSkill]
    # Links given a new address.
    links: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.added or self.links) or any(outcome.applied for outcome in self.outcomes)


def _add_skills(
    pdf: bytes, skills: list[SkillToAdd]
) -> tuple[bytes, list[AddedSkill], list[SkippedSkill]]:
    if not skills:
        return pdf, [], []
    names = list(dict.fromkeys(skill.name for skill in skills))
    try:
        result = editor.add_skills(
            pdf, names, {skill.name: skill.row for skill in skills if skill.row}
        )
    except editor.ResumeEditError:
        return (
            pdf,
            [],
            [
                SkippedSkill(skill=name, reason="no_room", message=_NO_SKILLS_SECTION)
                for name in names
            ],
        )
    readable = "\n".join(line.text for line in extract_lines(result.pdf))
    added = [
        AddedSkill(
            skill=item.skill,
            row=item.row,
            exact_font=item.exact_font,
            readable=editor.contains_skill(readable, item.skill),
        )
        for item in result.added
    ]
    skipped = [
        SkippedSkill(
            skill=item.skill,
            reason=item.reason,
            message=tailoring_service.SKIPPED_MESSAGES[item.reason],
        )
        for item in result.skipped
    ]
    return result.pdf, added, skipped


def _edit(pdf: bytes, payload: EditRequest) -> _Result:
    """Line edits first, then skills, so skills are placed against the final lines."""
    data, outcomes = engine.apply_edits(
        pdf,
        [_to_engine(edit) for edit in payload.edits],
        {link.link_id: link.uri for link in payload.links},
    )
    data, added, skipped = _add_skills(data, payload.skills)
    return _Result(
        pdf=data,
        outcomes=[
            EditOutcome(
                applied=outcome.applied,
                message=_message(edit, outcome),
                exact_font=outcome.exact_font,
            )
            for edit, outcome in zip(payload.edits, outcomes, strict=True)
        ],
        added=added,
        skipped=skipped,
        links=len(payload.links),
    )


async def _edit_safely(pdf: bytes, payload: EditRequest) -> _Result:
    """Runs the edit off the event loop and turns any failure into words.

    Edits are made on a copy, so the user's file is untouched when one fails;
    the real error is logged to be fixed.
    """
    try:
        return await asyncio.to_thread(_edit, pdf, payload)
    except editor.ResumeEditError as exc:
        raise ValidationFailedError(_UNREADABLE) from exc
    except Exception as exc:
        logger.exception("Editing a resume in the editor failed unexpectedly")
        raise ValidationFailedError(_FAILED) from exc


async def _stored(
    db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID
) -> tuple[ResumeFile, bytes]:
    resume = await _latest(db, user_id)
    if resume.id != resume_id:
        raise ConflictError(_REPLACED)
    return resume, await storage.get_file(resume.storage_key)


async def preview(db: AsyncSession, *, user_id: uuid.UUID, payload: EditRequest) -> EditedResume:
    """The resume with the edits made. Nothing is saved."""
    resume, original = await _stored(db, user_id, payload.resume_id)
    result = await _edit_safely(original, payload)
    pages = await asyncio.to_thread(editor.render_pages, result.pdf)
    return EditedResume(
        filename=resume.filename,
        outcomes=result.outcomes,
        added=result.added,
        skipped=result.skipped,
        pdf=_encode(result.pdf),
        pages=[_encode(page) for page in pages],
    )


async def save(db: AsyncSession, *, user_id: uuid.UUID, payload: EditRequest) -> ResumeRead:
    """Makes the edited copy the user's saved resume.

    The client sends the same edits it previewed, not a file: they are made
    again here on the stored resume, so what gets saved can only ever be the
    user's own resume with those edits. Skills added go onto the profile too.
    """
    resume, original = await _stored(db, user_id, payload.resume_id)
    result = await _edit_safely(original, payload)
    if not result.changed:
        raise ValidationFailedError("None of these changes could be made, so nothing was saved.")
    saved = await resumes_service.create_upload(
        db, user_id=user_id, filename=resume.filename, data=result.pdf
    )
    await tailoring_service.remember_skills(db, user_id, [item.skill for item in result.added])
    return saved


def _layout_for_assistant(pdf: bytes) -> tuple[engine.Layout, list[str] | None]:
    with engine.open_pdf(pdf) as doc:
        layout = engine.read_layout(doc)
        try:
            section = find_skills_section(doc)
            rows: list[str] | None = [entry.label for entry in section.entries if entry.label]
        except (NoSkillsSectionError, UnsupportedLayoutError):
            rows = None
    return layout, rows


async def assist(db: AsyncSession, *, user_id: uuid.UUID, payload: AssistRequest) -> AssistReply:
    """Turns the user's request into edits for the editor. Nothing is changed
    or saved here: the editor applies the edits to its draft, and the user saves.
    """
    assistant.check_rate(str(user_id))
    _resume, original = await _stored(db, user_id, payload.resume_id)
    try:
        layout, rows = await asyncio.to_thread(_layout_for_assistant, original)
    except Exception as exc:
        logger.exception("Reading a resume for the assistant failed unexpectedly")
        raise ValidationFailedError(_UNREADABLE) from exc

    profile = await profiles_service.get_profile(db, user_id=user_id)
    context = assistant.build_context(layout, rows, payload, assistant.profile_text(profile))
    # The user's own key goes first; Rolesetu's keys are the fallback.
    user_api_key = await get_decrypted_user_llm_key(db, user_id=user_id)
    started = time.monotonic()
    with ai_calls.called_by(user_id, "resume"):
        answer = await resume_assistant.propose_edits(context.prompt, user_api_key=user_api_key)
    edits = assistant.check_answer(answer, context)
    logger.info(
        "Resume assistant answered",
        extra={
            "prompt": resume_assistant.PROMPT_NAME,
            "seconds": round(time.monotonic() - started, 2),
            "edits_proposed": len(answer.edits),
            "edits_kept": len(edits),
            "edits_flagged": sum(1 for edit in edits if edit.unsupported),
        },
    )
    return AssistReply(reply=answer.reply.strip(), edits=edits)
