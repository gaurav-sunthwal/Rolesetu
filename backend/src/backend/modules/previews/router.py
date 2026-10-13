from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import client_ip
from backend.db.session import get_db
from backend.modules.previews import service
from backend.modules.previews.schemas import JobPreviewCreate, JobPreviewRead

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/job-previews", response_model=JobPreviewRead)
async def preview_job(
    payload: JobPreviewCreate,
    ip: str = Depends(client_ip),
    db: AsyncSession = Depends(get_db),
) -> JobPreviewRead:
    """No sign-in needed: this is what the landing page calls."""
    return await service.preview_job(db, url=payload.url, client_ip=ip)
