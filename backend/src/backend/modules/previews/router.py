from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.previews import service
from backend.modules.previews.schemas import JobPreviewCreate, JobPreviewRead

router = APIRouter(prefix="/public", tags=["public"])


def client_ip(request: Request) -> str:
    """The visitor's address, used only to rate limit them.

    Behind the host's proxy the socket address is the proxy's. The proxy passes
    the real one in X-Real-IP, or as the last entry of X-Forwarded-For (earlier
    entries are whatever the caller chose to send).
    """
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


@router.post("/job-previews", response_model=JobPreviewRead)
async def preview_job(
    payload: JobPreviewCreate,
    ip: str = Depends(client_ip),
    db: AsyncSession = Depends(get_db),
) -> JobPreviewRead:
    """No sign-in needed: this is what the landing page calls."""
    return await service.preview_job(db, url=payload.url, client_ip=ip)
