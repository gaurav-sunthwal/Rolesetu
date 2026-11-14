from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

QuestionKey = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$")]


class SavedAnswerWrite(BaseModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class LearnedAnswer(BaseModel):
    question_key: QuestionKey
    # Long enough for a written answer ("Why should we hire you?"): those are the
    # questions every form asks again, and the ones most worth not retyping.
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


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


class QuestionToMatch(BaseModel):
    """A question on a form that no saved answer is stored under."""

    key: QuestionKey
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class MatchQuestionsRequest(BaseModel):
    questions: Annotated[list[QuestionToMatch], Field(min_length=1, max_length=80)]


class QuestionMatchRead(BaseModel):
    """A saved answer to a question asked in other words."""

    # The asked question's key, as sent.
    key: str
    answer: str
    # The question the answer was saved for, shown so the user sees why it was offered.
    matched_key: str
    matched_question: str
    # "high": filled in. "medium": filled in as a draft for the user to check.
    confidence: Literal["high", "medium"]
