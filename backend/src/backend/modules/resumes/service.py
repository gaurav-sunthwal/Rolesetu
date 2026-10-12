import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import storage
from backend.core.exceptions import (
    ConflictError,
    NotFoundError,
    RateLimitedError,
    ValidationFailedError,
)
from backend.modules.profiles import service as profiles_service
from backend.modules.profiles.schemas import ProfileRead, ProfileWrite
from backend.modules.resumes import normalize, repository
from backend.modules.resumes.extraction import parser
from backend.modules.resumes.extraction.pdf_lines import UnreadablePdfError
from backend.modules.resumes.merge import ApplyMode, apply_resume
from backend.modules.resumes.models import ResumeFile
from backend.modules.resumes.schemas import DownloadLink, ResumeRead

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_UPLOADS_PER_HOUR = 10
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


async def read_pdf(data: bytes) -> ProfileWrite:
    """Reads a resume locally (no model call) into a cleaned profile."""
    try:
        # CPU-bound and blocking, so it runs off the event loop.
        raw = await asyncio.to_thread(parser.parse_pdf, data)
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

    profile = normalize.to_profile(raw)
    if not normalize.has_content(profile):
        raise ValidationFailedError(
            "We could not find skills, roles, projects or education in that PDF. "
            "Check that it is your resume and that its sections have clear headings "
            "such as Experience, Education and Skills."
        )
    return profile


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
    profile = await read_pdf(data)

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
