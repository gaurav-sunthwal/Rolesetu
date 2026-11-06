from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.domain_catalogs.models import DomainSkillCatalog

CATALOG_VERSION = 1


async def get(
    db: AsyncSession, field_key: str, *, version: int = CATALOG_VERSION
) -> DomainSkillCatalog | None:
    return await db.get(DomainSkillCatalog, (field_key, version))


async def upsert(
    db: AsyncSession,
    *,
    field_key: str,
    source: str,
    catalog_text: str,
    core_skill_names: list[str],
    version: int = CATALOG_VERSION,
) -> DomainSkillCatalog:
    row = await get(db, field_key, version=version)
    if row is None:
        row = DomainSkillCatalog(
            field_key=field_key,
            version=version,
            source=source,
            catalog_text=catalog_text,
            core_skill_names=core_skill_names,
        )
        db.add(row)
    else:
        row.source = source
        row.catalog_text = catalog_text
        row.core_skill_names = core_skill_names
    await db.flush()
    return row


async def list_all(db: AsyncSession, *, version: int = CATALOG_VERSION) -> list[DomainSkillCatalog]:
    stmt = (
        select(DomainSkillCatalog)
        .where(DomainSkillCatalog.version == version)
        .order_by(DomainSkillCatalog.field_key)
    )
    return list((await db.scalars(stmt)).all())


async def list_for_fields(
    db: AsyncSession, field_keys: set[str], *, version: int = CATALOG_VERSION
) -> list[DomainSkillCatalog]:
    if not field_keys:
        return []
    stmt = select(DomainSkillCatalog).where(
        DomainSkillCatalog.version == version,
        DomainSkillCatalog.field_key.in_(field_keys),
    )
    return list((await db.scalars(stmt)).all())
