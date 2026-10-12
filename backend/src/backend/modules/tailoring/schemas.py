from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

SkillName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class SkillToAdd(BaseModel):
    name: SkillName
    # The row of the Skills section to put it in ("Languages"). Chosen for the
    # user when left out.
    row: Annotated[str, StringConstraints(max_length=60)] | None = None


class Respell(BaseModel):
    """A skill already on the resume, to be written the way the job writes it."""

    written_as: SkillName
    wanted: SkillName


class TailorRequest(BaseModel):
    """The changes the user has chosen. Each is optional, but one is needed."""

    # Skills the user says they have and wants in the Skills section.
    skills: list[SkillToAdd] = Field(default_factory=list, max_length=12)
    # New wording for the role line under the user's name.
    headline: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)] | None
    ) = None
    respell: list[Respell] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _something_to_do(self) -> Self:
        if not (self.skills or self.headline or self.respell):
            raise ValueError("Choose at least one change to make.")
        return self


class AddedSkill(BaseModel):
    skill: str
    row: str | None
    # False when the resume's own font lacked a letter and a look-alike was used.
    exact_font: bool
    # Whether a text reader, like a job site's, finds the skill in the new file.
    readable: bool


class SkippedSkill(BaseModel):
    skill: str
    reason: Literal["already_listed", "no_room", "no_font"]
    message: str


class ChangeRead(BaseModel):
    """Existing text that was reworded, or why it could not be."""

    kind: Literal["headline", "respelled"]
    before: str
    after: str
    applied: bool
    message: str | None
    exact_font: bool


class TitleCheck(BaseModel):
    # The job's title, cleaned of locations and codes.
    wanted: str
    # Whether those exact words appear anywhere in the resume.
    present: bool
    # The role line under the user's name, if the resume has one.
    current: str | None
    # A rewording of that line to match the job, when one makes sense.
    suggested: str | None


class SkillKeyword(BaseModel):
    name: str
    required: bool
    status: Literal["present", "different_spelling", "missing"]
    # How the Skills section writes it, when that differs from the job's wording.
    written_as: str | None
    # Whether the user's profile already shows this skill.
    on_profile: bool


class KeywordCheck(BaseModel):
    """The job's wording compared with the words on the user's resume."""

    title: TitleCheck | None
    skills: list[SkillKeyword]


class KeptRead(BaseModel):
    """The updated copy is now the user's saved resume."""

    filename: str
    # Skills that went onto the resume, and so onto the profile.
    skills_added: list[str]


class TailoredRead(BaseModel):
    """The updated resume, handed straight back. Nothing is kept on the server:
    the browser holds the file until the user downloads or saves it.
    """

    filename: str
    added: list[AddedSkill]
    skipped: list[SkippedSkill]
    changes: list[ChangeRead]
    # Row labels of the Skills section, for moving a skill to a different row.
    rows: list[str]
    # The new PDF, base64-encoded.
    pdf: str
    # One base64-encoded PNG per page, before and after the change.
    before: list[str]
    after: list[str]
