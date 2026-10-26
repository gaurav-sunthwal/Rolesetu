from datetime import datetime

from pydantic import BaseModel


class ShareCreate(BaseModel):
    # Off by default: someone proud of a score may not want their gaps public.
    show_gaps: bool = False


class ShareRead(BaseModel):
    """A public match card. The same fields are what anyone with the link sees."""

    slug: str
    role: str | None
    company: str | None
    score: int
    matched: list[str]
    gaps: list[str]
    created_at: datetime
