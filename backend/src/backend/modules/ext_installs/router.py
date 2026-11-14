from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import client_ip
from backend.core.config import get_settings
from backend.db.session import get_db
from backend.modules.ext_installs import service
from backend.modules.ext_installs.schemas import InstallEventsWrite

# No sign-in on these: they follow installs that have no account yet.
router = APIRouter(prefix="/extension/installs", tags=["extension"])

_INSTALL_ID = r"^[0-9a-f-]{36}$"


@router.post("/events", status_code=204)
async def record_install_events(
    payload: InstallEventsWrite,
    ip: str = Depends(client_ip),
    db: AsyncSession = Depends(get_db),
) -> None:
    """An install's steps before it is connected: from the extension (installed,
    setup opened...) and from the website's setup pages (page seen, signed in...).
    """
    await service.record(db, payload, ip)


@router.get("/{install_id}/uninstalled", response_class=RedirectResponse, status_code=303)
async def install_removed(
    install_id: Annotated[str, Path(pattern=_INSTALL_ID)],
    v: Annotated[str | None, Query(max_length=20, pattern=r"^[0-9.]+$")] = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Chrome opens this when the extension is removed. It records the removal and
    sends the person on to a page asking why (one click, optional)."""
    await service.uninstalled(db, install_id, v)
    return RedirectResponse(
        f"{get_settings().dashboard_url}/goodbye?install={install_id}", status_code=303
    )
