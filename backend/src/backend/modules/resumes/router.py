import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.resumes import service
from backend.modules.resumes.schemas import DownloadLink, ResumeApplied, ResumeApply, ResumeRead
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("", response_model=ResumeRead, status_code=201)
async def upload_resume(
    file: UploadFile,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeRead:
    """Reads the PDF and returns what was found. Reading is local and takes
    milliseconds, so there is no background job to wait for.
    """
    # One byte over the limit is enough to know it is too big, without
    # reading an arbitrarily large upload into memory.
    data = await file.read(service.MAX_FILE_BYTES + 1)
    return await service.create_upload(db, user_id=user.id, filename=file.filename, data=data)


@router.get("/latest", response_model=ResumeRead | None)
async def read_latest_resume(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ResumeRead | None:
    return await service.get_latest(db, user_id=user.id)


@router.get("/{resume_id}", response_model=ResumeRead)
async def read_resume(
    resume_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeRead:
    return await service.get_resume(db, user_id=user.id, resume_id=resume_id)


@router.post("/{resume_id}/apply", response_model=ResumeApplied)
async def apply_resume_to_profile(
    resume_id: uuid.UUID,
    payload: ResumeApply,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeApplied:
    resume, profile = await service.apply_to_profile(
        db, user_id=user.id, resume_id=resume_id, mode=payload.mode
    )
    return ResumeApplied(resume=resume, profile=profile)


@router.get("/{resume_id}/download-link", response_model=DownloadLink)
async def read_download_link(
    resume_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> DownloadLink:
    return await service.download_link(db, user_id=user.id, resume_id=resume_id)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_resume(db, user_id=user.id, resume_id=resume_id)
