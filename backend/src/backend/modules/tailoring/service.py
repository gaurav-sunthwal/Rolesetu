import asyncio
import base64
import uuid

import pymupdf
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import storage
from backend.core.exceptions import NotFoundError, ValidationFailedError
from backend.modules.matches import repository as matches_repository
from backend.modules.profiles import service as profiles_service
from backend.modules.profiles.schemas import ProfileWrite, SkillItem
from backend.modules.resumes import repository as resumes_repository
from backend.modules.resumes import service as resumes_service
from backend.modules.resumes.extraction.pdf_lines import extract_lines
from backend.modules.tailoring import keywords
from backend.modules.tailoring.pdf import editor
from backend.modules.tailoring.pdf.section import (
    NoSkillsSectionError,
    UnsupportedLayoutError,
    find_skills_section,
    read_lines,
)
from backend.modules.tailoring.schemas import (
    AddedSkill,
    ChangeRead,
    KeptRead,
    KeywordCheck,
    SkillKeyword,
    SkippedSkill,
    TailoredRead,
    TailorRequest,
    TitleCheck,
)

# The profile's own cap on skills (see ProfileWrite.skills).
MAX_PROFILE_SKILLS = 100

_CANNOT_EDIT = {
    "no_skills_section": (
        "We could not find a Skills section in your resume, so there is nowhere to add "
        "these. Add a section headed “Skills” to your resume and upload it again."
    ),
    "unsupported_layout": (
        "Your resume lists one skill per line. Adding to that layout is not supported "
        "yet. A resume that lists skills in a row (“Python, SQL, React”) works."
    ),
    "unreadable": "Your stored resume could not be opened. Please upload it again.",
}
_SKIPPED = {
    "already_listed": "Already in your Skills section.",
    "no_room": (
        "No room: the row is full and the page has no space for another line. "
        "Try a different row, or remove a skill this job does not ask for."
    ),
    "no_font": "Your resume's font cannot write this, and no matching font is installed.",
}
_NOT_CHANGED = {
    ("headline", "not_found"): "Your resume has no role line under your name to change.",
    ("respelled", "not_found"): "That word could not be found in your Skills section.",
    "no_room": "The new wording is too long for its line.",
    "no_font": "Your resume's font cannot write this, and no matching font is installed.",
    "unsafe": "Changing this line would have disturbed the text around it, so it was left alone.",
}


def _why_not(change: editor.Change) -> str | None:
    if change.applied or change.reason is None:
        return None
    return _NOT_CHANGED.get((change.kind, change.reason)) or _NOT_CHANGED[change.reason]


def _edit(
    pdf: bytes, payload: TailorRequest
) -> tuple[editor.EditResult, list[bytes], list[bytes], str, list[str]]:
    """Everything that needs the CPU, done in one go off the event loop."""
    result = editor.tailor(
        pdf,
        skills=list(dict.fromkeys(skill.name for skill in payload.skills)),
        chosen_rows={skill.name: skill.row for skill in payload.skills if skill.row},
        headline=payload.headline,
        respell=[(item.written_as, item.wanted) for item in payload.respell],
    )
    readable_text = "\n".join(line.text for line in extract_lines(result.pdf))
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        try:
            labels = [entry.label for entry in find_skills_section(doc).entries if entry.label]
        except (NoSkillsSectionError, UnsupportedLayoutError):
            labels = []  # only the headline was changed; there are no rows to offer
    return (
        result,
        editor.render_pages(pdf),
        editor.render_pages(result.pdf),
        readable_text,
        labels,
    )


async def _remember_skills(db: AsyncSession, user_id: uuid.UUID, skills: list[str]) -> None:
    """Puts skills that are now on the saved resume onto the profile, so the
    resume and the profile (which job scores are worked out from) always agree.
    """
    profile = await profiles_service.get_profile(db, user_id=user_id)
    known = {skill.name.lower() for skill in profile.skills}
    new = [name for name in skills if name.lower() not in known]
    if not new:
        return
    payload = ProfileWrite.model_validate(
        profile.model_dump(exclude={"version", "completeness", "updated_at"})
    )
    for name in new[: max(0, MAX_PROFILE_SKILLS - len(payload.skills))]:
        payload.skills.append(SkillItem(id=uuid.uuid4().hex, name=name))
    await profiles_service.save_profile(db, user_id=user_id, payload=payload)


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


async def create(db: AsyncSession, *, user_id: uuid.UUID, payload: TailorRequest) -> TailoredRead:
    """Builds the updated resume and returns it as a preview. Nothing is saved
    and the profile is not touched: that happens only in `keep`.
    """
    resume = await resumes_repository.latest(db, user_id)
    if resume is None:
        raise NotFoundError("Upload your resume first, then we can add skills to it.")

    original = await storage.get_file(resume.storage_key)
    try:
        result, before, after, readable_text, labels = await asyncio.to_thread(
            _edit, original, payload
        )
    except editor.ResumeEditError as exc:
        raise ValidationFailedError(_CANNOT_EDIT[exc.reason]) from exc

    if not result.added and not any(change.applied for change in result.changes):
        reasons = [f"{item.skill}: {_SKIPPED[item.reason]}" for item in result.skipped] + [
            f"{change.after}: {_why_not(change)}" for change in result.changes
        ]
        raise ValidationFailedError(
            f"Nothing could be changed on your resume. {'; '.join(reasons)}"
        )

    return TailoredRead(
        filename=resume.filename,
        added=[
            AddedSkill(
                skill=item.skill,
                row=item.row,
                exact_font=item.exact_font,
                readable=editor.contains_skill(readable_text, item.skill),
            )
            for item in result.added
        ],
        skipped=[
            SkippedSkill(skill=item.skill, reason=item.reason, message=_SKIPPED[item.reason])
            for item in result.skipped
        ],
        changes=[
            ChangeRead(
                kind=change.kind,
                before=change.before,
                after=change.after,
                applied=change.applied,
                message=_why_not(change),
                exact_font=change.exact_font,
            )
            for change in result.changes
        ],
        rows=labels,
        pdf=_encode(result.pdf),
        before=[_encode(page) for page in before],
        after=[_encode(page) for page in after],
    )


async def keep(db: AsyncSession, *, user_id: uuid.UUID, payload: TailorRequest) -> KeptRead:
    """Makes the updated copy the user's saved resume, and puts the skills that
    were added to it on their profile.

    The client sends the same choices it previewed, not a file: the edit is
    repeated here on the stored resume, so what gets saved can only ever be the
    user's own resume with those changes.
    """
    resume = await resumes_repository.latest(db, user_id)
    if resume is None:
        raise NotFoundError("Upload your resume first, then we can add skills to it.")
    original = await storage.get_file(resume.storage_key)
    try:
        result, _before, _after, _text, _labels = await asyncio.to_thread(_edit, original, payload)
    except editor.ResumeEditError as exc:
        raise ValidationFailedError(_CANNOT_EDIT[exc.reason]) from exc
    if not result.added and not any(change.applied for change in result.changes):
        raise ValidationFailedError("Nothing could be changed on your resume, so it was not saved.")

    saved = await resumes_service.create_upload(
        db, user_id=user_id, filename=resume.filename, data=result.pdf
    )
    added = [item.skill for item in result.added]
    await _remember_skills(db, user_id, added)
    return KeptRead(filename=saved.filename, skills_added=added)


def _compare(
    pdf: bytes, job_title: str | None, skills: list[tuple[str, bool, bool]]
) -> KeywordCheck:
    """`skills` are (name, required, on_profile) as the job check judged them."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        resume_text = "\n".join(page.get_text() for page in doc)
        first_page = read_lines(doc[0]) if doc.page_count else []
        try:
            section = find_skills_section(doc)
            section_text = " ".join(entry.text for entry in section.entries)
        except (NoSkillsSectionError, UnsupportedLayoutError):
            section_text = ""

    title = None
    if job_title and keywords.clean_title(job_title):
        headline = keywords.find_headline(first_page)
        present = keywords.title_present(job_title, resume_text)
        title = TitleCheck(
            wanted=keywords.clean_title(job_title),
            present=present,
            current=headline.role if headline else None,
            suggested=(
                keywords.suggest_headline(headline.role, job_title)
                if headline and not present
                else None
            ),
        )

    checked: list[SkillKeyword] = []
    for name, required, on_profile in skills:
        found = keywords.check_skill(name, resume_text)
        status, written_as = found.status, None
        if status == "different_spelling":
            # Respelling is only done inside the Skills section. A different
            # spelling elsewhere means the job's own word is simply missing.
            in_section = keywords.check_skill(name, section_text)
            if in_section.status == "different_spelling":
                written_as = in_section.written_as
            else:
                status = "missing"
        checked.append(
            SkillKeyword(
                name=name,
                required=required,
                status=status,
                written_as=written_as,
                on_profile=on_profile,
            )
        )
    return KeywordCheck(title=title, skills=checked)


async def check_keywords(
    db: AsyncSession, *, user_id: uuid.UUID, match_id: uuid.UUID
) -> KeywordCheck:
    """How the job's title and skills compare with the words on the resume."""
    match = await matches_repository.get(db, user_id, match_id)
    if match is None:
        raise NotFoundError("That job check no longer exists.")
    resume = await resumes_repository.latest(db, user_id)
    if resume is None:
        raise NotFoundError("Upload your resume first, then we can compare it with this job.")
    skills = [
        (str(item["name"]), bool(item.get("required")), item.get("verdict") != "missing")
        for item in match.skill_results
    ]
    pdf = await storage.get_file(resume.storage_key)
    try:
        return await asyncio.to_thread(_compare, pdf, match.job.role, skills)
    except Exception as exc:  # noqa: BLE001 - a file that cannot be opened has one explanation
        raise ValidationFailedError(_CANNOT_EDIT["unreadable"]) from exc
