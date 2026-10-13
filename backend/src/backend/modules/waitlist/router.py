from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import client_ip
from backend.db.session import get_db
from backend.modules.waitlist import service
from backend.modules.waitlist.schemas import WaitlistJoin, WaitlistJoined

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/extension-waitlist", response_model=WaitlistJoined)
async def join_waitlist(
    payload: WaitlistJoin,
    background_tasks: BackgroundTasks,
    ip: str = Depends(client_ip),
    db: AsyncSession = Depends(get_db),
) -> WaitlistJoined:
    """No sign-in needed: asks to be emailed when the extension is released."""
    new_address = await service.join(db, email=payload.email, client_ip=ip)
    if new_address:
        background_tasks.add_task(service.send_welcome, new_address)
    return WaitlistJoined()
