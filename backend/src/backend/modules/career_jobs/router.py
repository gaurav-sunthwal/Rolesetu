from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.career_jobs import service
from backend.modules.career_jobs.schemas import (
    CareerCompany,
    CareerCompanyAdd,
    CareerCompanyList,
    CareerJobPage,
)
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/career-jobs", tags=["career-jobs"])


@router.get("/companies", response_model=CareerCompanyList)
async def list_companies(
    _: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> CareerCompanyList:
    return await service.list_companies(db)


@router.post("/companies", response_model=CareerCompany, status_code=201)
async def add_company(
    payload: CareerCompanyAdd,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> CareerCompany:
    """Reads the company's careers site straight away, so its jobs show at once.
    Limited per user, because every added site is read daily for everyone."""
    return await service.add_company(db, payload.link, user_id=user.id)


@router.get("", response_model=CareerJobPage)
async def list_jobs(
    companies: Annotated[list[str] | None, Query(max_length=200)] = None,
    places: Annotated[list[str] | None, Query(max_length=50)] = None,
    include_stretch: bool = True,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> CareerJobPage:
    return await service.list_jobs(
        db,
        user_id=user.id,
        companies=companies or [],
        places=places or [],
        include_stretch=include_stretch,
        cursor=cursor,
        limit=limit,
    )
