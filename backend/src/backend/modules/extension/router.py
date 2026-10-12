from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.extension import service
from backend.modules.extension.schemas import AutofillData, ExtensionConnected, ExtensionStatus
from backend.modules.matches import scoring
from backend.modules.profiles import service as profiles_service
from backend.modules.saved_answers import service as saved_answers_service
from backend.modules.users.dependencies import get_db_user, get_db_user_or_extension
from backend.modules.users.models import User

# Managing the connection is done from the dashboard only: those routes use
# `get_db_user`, which refuses a request signed with an extension key. Reading
# the autofill data is the one thing here the extension itself may do.
router = APIRouter(prefix="/extension", tags=["extension"])


@router.post("/connect", response_model=ExtensionConnected, status_code=201)
async def connect_extension(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ExtensionConnected:
    token, row = await service.connect(db, user_id=user.id)
    return ExtensionConnected(token=token, connected_at=row.created_at)


@router.get("/status", response_model=ExtensionStatus)
async def read_extension_status(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ExtensionStatus:
    row = await service.get_connection(db, user_id=user.id)
    return ExtensionStatus(
        connected=row is not None,
        connected_at=row.created_at if row else None,
        last_used_at=row.last_used_at if row else None,
    )


@router.delete("/connection", status_code=204)
async def disconnect_extension(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.disconnect(db, user_id=user.id)


@router.get("/autofill", response_model=AutofillData)
async def read_autofill_data(
    user: User = Depends(get_db_user_or_extension), db: AsyncSession = Depends(get_db)
) -> AutofillData:
    profile = await profiles_service.get_profile(db, user_id=user.id)
    answers = await saved_answers_service.list_answers(db, user_id=user.id)
    years = scoring.years_of_experience(
        [(role.start, role.end) for role in profile.experience if role.start],
        datetime.now(UTC).date(),
    )
    return AutofillData(
        email=user.email,
        profile=profile,
        saved_answers={answer.question_key: answer.answer for answer in answers},
        years_of_experience=years,
    )
