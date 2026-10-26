from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

QuestionKey = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$")]


class SavedAnswerWrite(BaseModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class LearnedAnswer(BaseModel):
    question_key: QuestionKey
    # Short: a learned answer is a fact (a date, a city, a choice), not an essay.
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class LearnedAnswersWrite(BaseModel):
    """Answers the user typed into an application form, sent by the extension."""

    answers: Annotated[list[LearnedAnswer], Field(min_length=1, max_length=20)]


class LearnedAnswerRead(BaseModel):
    question_key: str
    # What was saved before, so the extension can offer Undo. None: it was new.
    previous: str | None


class SavedAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_key: str
    answer: str
    updated_at: datetime
