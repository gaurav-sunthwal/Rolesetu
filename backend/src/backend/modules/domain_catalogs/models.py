from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class DomainSkillCatalog(Base):
    __tablename__ = "domain_skill_catalogs"

    field_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    catalog_text: Mapped[str] = mapped_column(Text)
    core_skill_names: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
