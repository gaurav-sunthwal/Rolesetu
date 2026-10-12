from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LlmKeySet(BaseModel):
    api_key: str = Field(min_length=10)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LlmKeyStatus(BaseModel):
    has_key: bool
    updated_at: datetime | None = None
