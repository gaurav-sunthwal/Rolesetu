from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreditsRead(BaseModel):
    plan: Literal["free", "pro"]
    used: int
    limit: int = Field(description="Credits this plan gives per calendar month (UTC).")
    left: int
    resets_at: datetime
    pro_limit: int = Field(description="What Pro gives, to show next to an upgrade.")
    costs: dict[str, int] = Field(description="Credits each AI action costs.")
