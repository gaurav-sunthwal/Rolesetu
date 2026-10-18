from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.resume_editor import service
from backend.modules.resume_editor.schemas import (
    AssistReply,
    AssistRequest,
    EditedResume,
    EditRequest,
    ResumeLayout,
)
from backend.modules.resumes.schemas import ResumeRead
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/resume-editor", tags=["resume-editor"])


@router.get("", response_model=ResumeLayout)
async def read_resume_layout(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ResumeLayout:
    """The saved resume as sections of lines, with a picture of each page."""
    return await service.get_layout(db, user_id=user.id)


@router.post("/preview", response_model=EditedResume)
async def preview_resume_edits(
    payload: EditRequest,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> EditedResume:
    """The resume with the edits made, in its own fonts and layout. Nothing is
    stored. Editing is local and takes a fraction of a second, so there is no
    background job.
    """
    return await service.preview(db, user_id=user.id, payload=payload)


@router.post("/save", response_model=ResumeRead)
async def save_resume_edits(
    payload: EditRequest,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeRead:
    """Makes the edits again on the saved resume and keeps the result as the
    user's resume, replacing the one on file.
    """
    return await service.save(db, user_id=user.id, payload=payload)


@router.post("/assist", response_model=AssistReply)
async def ask_resume_assistant(
    payload: AssistRequest,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> AssistReply:
    """Turns a request in plain words ("add my Rolesetu project") into edits to
    the resume's lines. The editor applies them to its draft; nothing is saved.
    The model call takes a few seconds, like a job check, so it is answered
    directly rather than through a background job.
    """
    return await service.assist(db, user_id=user.id, payload=payload)
