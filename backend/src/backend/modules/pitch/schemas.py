from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from backend.modules.saved_answers.schemas import QuestionKey

ShortName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]


class PitchQuestion(BaseModel):
    key: QuestionKey
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    # The heading and words of the pop-up around the box, when the box's own label
    # says little ("Your message" under "Reach out to the team at Encord").
    context: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""


class PitchAnswersRequest(BaseModel):
    """A form's written questions, with the job the user is applying to."""

    questions: Annotated[list[PitchQuestion], Field(min_length=1, max_length=10)]
    company: ShortName | None = None
    role: ShortName | None = None
    # The posting, used only to choose which of the user's own facts come first.
    job_text: Annotated[str, StringConstraints(max_length=20000)] = ""


class PitchAnswerRead(BaseModel):
    key: str
    kind: Literal["why_company", "why_hire", "about_you", "note_to_founder"]
    text: str
    # "your_answer": the user's saved answer, with this company's names put in.
    # "profile": written from the profile, for the user to check and make their own.
    source: Literal["your_answer", "profile"]
    # What it was built from (skills, project, employer), to show why it says what it says.
    uses: list[str]
    # The company the answer names: the one sent, or else the one the pop-up named.
    company: str | None


class AiAnswerRequest(BaseModel):
    """One box to write, or improve, with the model."""

    mode: Literal["write", "improve"]
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    context: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""
    company: ShortName | None = None
    role: ShortName | None = None
    job_text: Annotated[str, StringConstraints(max_length=20000)] = ""
    # What is in the box now (for "improve").
    current: Annotated[str, StringConstraints(max_length=5000)] = ""
    # The box's own limit (its maxlength), when it has one.
    max_length: int = Field(default=2000, ge=20, le=5000)


class AiUsageRead(BaseModel):
    # AI credits left this month. Still nullable so extensions built before credits
    # (which read null as "unlimited") keep parsing it.
    left: int | None
    # Credits the plan gives per month.
    limit: int


class AiAnswerRead(BaseModel):
    text: str
    # Claims the check took out because nothing the user wrote or saved backs them.
    removed: list[str]
    usage: AiUsageRead
