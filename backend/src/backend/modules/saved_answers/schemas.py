from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

QuestionKey = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$")]


class SavedAnswerWrite(BaseModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SavedAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_key: str
    answer: str
    updated_at: datetime
