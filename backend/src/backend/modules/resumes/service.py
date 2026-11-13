import asyncio
import logging
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.profile_understanding import understand_profile
from backend.core import storage
from backend.core.exceptions import (
    ConflictError,
    NotFoundError,
    RateLimitedError,
    ValidationFailedError,
)
from backend.modules.ai_calls.service import called_by
from backend.modules.llm_keys.service import get_decrypted_user_llm_key
from backend.modules.matches.local.semantic import usable_lines, warm_up_chunks
from backend.modules.profiles import service as profiles_service
from backend.modules.profiles.field_detection import resolve_field
from backend.modules.profiles.schemas import ProfileRead, ProfileWrite, SkillItem
from backend.modules.resumes import normalize, repository
from backend.modules.resumes.extraction import parser
from backend.modules.resumes.extraction.pdf_lines import UnreadablePdfError, extract_lines
from backend.modules.resumes.merge import ApplyMode, apply_resume
from backend.modules.resumes.models import ResumeFile
from backend.modules.resumes.normalize import MAX_SKILLS as MAX_PROFILE_SKILLS
from backend.modules.resumes.schemas import DownloadLink, ResumeIdentity, ResumeRead

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_UPLOADS_PER_HOUR = 10
# Re-reading a resume calls the model for the person's field. Twice a day is enough.
MAX_RESUME_READS_PER_DAY = 2
DOWNLOAD_LINK_SECONDS = 300
_PDF_MAGIC = b"%PDF-"


def to_read(resume: ResumeFile) -> ResumeRead:
    return ResumeRead(
        id=resume.id,
        filename=resume.filename,
        size_bytes=resume.size_bytes,
        status=resume.status,  # type: ignore[arg-type]
        error=resume.error,
        parsed=ProfileWrite.model_validate(resume.parsed_json) if resume.parsed_json else None,
        applied_at=resume.applied_at,
        created_at=resume.created_at,
    )


def _safe_filename(name: str | None) -> str:
    base = (name or "resume.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[^\w.\- ()]+", "_", base).strip(" .") or "resume.pdf"
    if not base.lower().endswith(".pdf"):
        base = f"{base}.pdf"
    return base[:120]


def validate_pdf(data: bytes) -> None:
    if len(data) == 0:
        raise ValidationFailedError("That file is empty. Choose your resume PDF and try again.")
    if len(data) > MAX_FILE_BYTES:
        raise ValidationFailedError(
            "That file is larger than 5 MB. Export a smaller PDF and retry."
        )
    # Check the content, not the name or the browser's claimed type.
    if not data.startswith(_PDF_MAGIC):
        raise ValidationFailedError(
            "That is not a PDF. Export your resume as a PDF and upload that."
        )


async def _remove(db: AsyncSession, resume: ResumeFile) -> None:
    await storage.delete_file(resume.storage_key)
    await db.delete(resume)


async def _run_parser[T](read: Callable[[bytes], T], data: bytes) -> T:
    try:
        # CPU-bound and blocking, so it runs off the event loop.
        return await asyncio.to_thread(read, data)
    except parser.NoTextInPdfError as exc:
        raise ValidationFailedError(
            "This PDF has no selectable text, so it looks like a scan or a photo. "
            "Export your resume as a text PDF (from Word, Google Docs or your resume "
            "builder) and upload that."
        ) from exc
    except UnreadablePdfError as exc:
        raise ValidationFailedError(
            "This PDF could not be opened. It may be damaged or password-protected."
        ) from exc


async def read_pdf(data: bytes, user_api_key: str | None = None) -> ProfileWrite:
    """Reads a resume into a cleaned profile with AI-assisted understanding."""
    raw = await _run_parser(parser.parse_pdf, data)
    profile = normalize.to_profile(raw)

    # AI-assisted profile understanding: extract domain, scope, and categorized skills
    try:
        raw_lines = await _run_parser(extract_lines, data)
        full_text = "\n".join(line.text for line in raw_lines)
        ai_profile = await understand_profile(full_text, user_api_key=user_api_key)
        if ai_profile is not None:
            existing = {s.name.lower() for s in profile.skills}
            # Gather all categorized and flat skills
            all_ai_skills = list(ai_profile.skills)
            for cat_list in [
                ai_profile.categorized_skills.hr_administrative,
                ai_profile.categorized_skills.organisational,
                ai_profile.categorized_skills.interpersonal,
                ai_profile.categorized_skills.analytical,
                ai_profile.categorized_skills.professional,
                ai_profile.categorized_skills.technical_software,
            ]:
                all_ai_skills.extend(cat_list)

            for skill_name in all_ai_skills:
                clean = skill_name.strip()
                if (
                    clean
                    and clean.lower() not in existing
                    and len(profile.skills) < MAX_PROFILE_SKILLS
                ):
                    profile.skills.append(SkillItem(id=uuid.uuid4().hex, name=clean[:60]))
                    existing.add(clean.lower())

            if not profile.headline and ai_profile.headline:
                profile.headline = ai_profile.headline

            field_key, scope_summary, inferred = resolve_field(profile, ai_profile)
            if field_key and not profile.field_key:
                profile.field_key = field_key
            if scope_summary and not profile.scope_summary:
                profile.scope_summary = scope_summary
            if inferred and not profile.inferred_field_key:
                profile.inferred_field_key = inferred

            # Warm up embeddings for semantic matcher
            chunks = list(ai_profile.scope_chunks)
            for exp in profile.experience:
                chunks.extend(usable_lines(exp.description))
            warm_up_chunks(chunks)
    except Exception:
        logger.exception("AI profile enrichment failed; continuing with locally parsed profile")

    if not normalize.has_content(profile):
        raise ValidationFailedError(
            "We could not find skills, roles, projects or education in that PDF. "
            "Check that it is your resume and that its sections have clear headings "
            "such as Experience, Education and Skills."
        )
    return profile


async def read_identity(data: bytes) -> ResumeIdentity:
    """The email and first name on a resume, for signing up with it. Runs
    before sign-in, so the file is read in memory and never stored.
    """
    validate_pdf(data)
    identity = await _run_parser(parser.read_identity, data)
    first_name = identity.full_name.split()[0] if identity.full_name else None
    return ResumeIdentity(email=identity.email, first_name=first_name)


async def create_upload(
    db: AsyncSession, *, user_id: uuid.UUID, filename: str | None, data: bytes
) -> ResumeRead:
    """Reads the PDF, then stores it. A file that cannot be read is rejected
    before anything is saved, so nothing unusable is ever kept.
    """
    validate_pdf(data)
    now = datetime.now(UTC)
    if await repository.count_since(db, user_id, now - timedelta(hours=1)) >= MAX_UPLOADS_PER_HOUR:
        raise RateLimitedError(
            f"You have uploaded {MAX_UPLOADS_PER_HOUR} resumes in the last hour. "
            "Please wait a little before uploading another."
        )
    if (
        await repository.count_since(db, user_id, now - timedelta(days=1))
        >= MAX_RESUME_READS_PER_DAY
    ):
        raise RateLimitedError("You can update your resume twice a day. Try again tomorrow.")
    user_api_key = await get_decrypted_user_llm_key(db, user_id=user_id)
    with called_by(user_id, "resume"):
        profile = await read_pdf(data, user_api_key=user_api_key)

    resume_id = uuid.uuid4()
    storage_key = f"resumes/{user_id}/{resume_id}.pdf"
    await storage.put_file(storage_key, data, content_type="application/pdf")

    # One resume per person: the new upload replaces any earlier file.
    for previous in await repository.list_for_user(db, user_id):
        await _remove(db, previous)

    resume = ResumeFile(
        id=resume_id,
        user_id=user_id,
        storage_key=storage_key,
        filename=_safe_filename(filename),
        size_bytes=len(data),
        status="parsed",
        parsed_json=profile.model_dump(mode="json"),
        parser_version=parser.PARSER_VERSION,
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)
    return to_read(resume)


async def get_latest(db: AsyncSession, *, user_id: uuid.UUID) -> ResumeRead | None:
    resume = await repository.latest(db, user_id)
    return to_read(resume) if resume else None


async def _require(db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID) -> ResumeFile:
    resume = await repository.get(db, user_id, resume_id)
    if resume is None:
        raise NotFoundError("Resume not found")
    return resume


async def get_resume(db: AsyncSession, *, user_id: uuid.UUID, resume_id: uuid.UUID) -> ResumeRead:
    return to_read(await _require(db, user_id, resume_id))


async def apply_to_profile(
    db: AsyncSession, *, user_id: uuid.UUID, resume_id: uuid.UUID, mode: ApplyMode
) -> tuple[ResumeRead, ProfileRead]:
    resume = await _require(db, user_id, resume_id)
    if resume.status != "parsed" or not resume.parsed_json:
        raise ConflictError("This resume has not been read yet, so there is nothing to apply.")

    parsed = ProfileWrite.model_validate(resume.parsed_json)
    current = await profiles_service.get_profile(db, user_id=user_id)
    current_write = ProfileWrite.model_validate(
        current.model_dump(exclude={"version", "completeness", "updated_at"})
    )
    profile = await profiles_service.save_profile(
        db, user_id=user_id, payload=apply_resume(current_write, parsed, mode)
    )
    chunks = [line for exp in profile.experience for line in usable_lines(exp.description)]
    if chunks:
        warm_up_chunks(chunks)
    resume.applied_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(resume)
    return to_read(resume), profile


async def download_link(
    db: AsyncSession, *, user_id: uuid.UUID, resume_id: uuid.UUID
) -> DownloadLink:
    resume = await _require(db, user_id, resume_id)
    url = await storage.signed_download_url(
        resume.storage_key, filename=resume.filename, expires_in=DOWNLOAD_LINK_SECONDS
    )
    return DownloadLink(url=url, expires_in=DOWNLOAD_LINK_SECONDS)


async def delete_resume(db: AsyncSession, *, user_id: uuid.UUID, resume_id: uuid.UUID) -> None:
    await _remove(db, await _require(db, user_id, resume_id))
