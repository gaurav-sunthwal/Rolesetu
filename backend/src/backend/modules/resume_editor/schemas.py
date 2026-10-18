import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from backend.modules.tailoring.schemas import AddedSkill, SkillToAdd, SkippedSkill

LineId = Annotated[str, StringConstraints(pattern=r"^\d{1,3}-\d{1,4}$")]


LinkId = Annotated[str, StringConstraints(pattern=r"^\d{1,3}-L\d{1,4}$")]
# Addresses a resume links to: web pages, email and phone.
Uri = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=500, pattern=r"^(?:https?://\S+|mailto:\S+|tel:\S+)$"
    ),
]


class EditorLink(BaseModel):
    """A link over some words of a line."""

    id: str
    # The words it is drawn over, and where clicking them goes.
    text: str
    uri: str


class EditorLine(BaseModel):
    """One line of the resume as it is drawn on the page."""

    id: str
    # The words that can be changed. A bullet in front is kept apart, in `bullet`.
    text: str
    # Whether the line starts with a bullet (written or drawn).
    bullet: bool
    heading: bool
    bold: bool
    italic: bool
    # Sits at the right margin, like a date or a place.
    right_aligned: bool
    # False on pages laid out in columns, where lines cannot be added yet.
    can_add_below: bool
    page: int
    # Where the line is on its page, in points from the top-left: x0, y0, x1, y1.
    box: tuple[float, float, float, float]
    links: list[EditorLink] = Field(default_factory=list)


class EditorSection(BaseModel):
    title: str
    # The Skills section, where skills can be added the way job checks add them.
    is_skills: bool
    lines: list[EditorLine]


class EditorPage(BaseModel):
    width: float
    height: float
    # The page as a base64-encoded PNG.
    image: str


class ResumeLayout(BaseModel):
    """The user's saved resume, read as sections of lines they can edit."""

    resume_id: uuid.UUID
    filename: str
    pages: list[EditorPage]
    sections: list[EditorSection]
    # Row labels of the Skills section ("Languages"), for choosing where a skill goes.
    skill_rows: list[str]


class LineEdit(BaseModel):
    kind: Literal["change", "remove", "add_below"]
    line_id: LineId
    # The line's new words (change), or the new line's words (add_below).
    text: Annotated[str, StringConstraints(max_length=400)] = ""
    # add_below only: an existing line whose look the new line copies, instead
    # of the line it goes under (a new project's title under the last bullet).
    style_line_id: LineId | None = None

    @model_validator(mode="after")
    def _has_words(self) -> Self:
        if self.kind == "add_below" and not self.text.strip():
            raise ValueError("A new line needs some words.")
        return self


class LinkEdit(BaseModel):
    """A new address for one of the resume's links."""

    link_id: LinkId
    uri: Uri


class EditRequest(BaseModel):
    """The user's edits, always against the resume they opened (`resume_id`)."""

    resume_id: uuid.UUID
    edits: list[LineEdit] = Field(default_factory=list, max_length=80)
    skills: list[SkillToAdd] = Field(default_factory=list, max_length=12)
    links: list[LinkEdit] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def _something_to_do(self) -> Self:
        if not (self.edits or self.skills or self.links):
            raise ValueError("Make at least one change to your resume.")
        return self


class EditOutcome(BaseModel):
    applied: bool
    # Why not, in plain words, when it was not applied.
    message: str | None
    # False when the resume's own font lacked a letter and a look-alike was used.
    exact_font: bool


class EditedResume(BaseModel):
    """The edited resume, handed straight back. Nothing is kept on the server."""

    filename: str
    # One per edit, in the order they were sent.
    outcomes: list[EditOutcome]
    added: list[AddedSkill]
    skipped: list[SkippedSkill]
    # The new PDF, base64-encoded.
    pdf: str
    # One base64-encoded PNG per page.
    pages: list[str]


Words = Annotated[str, StringConstraints(max_length=400)]
NewLineKey = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class DraftNewLine(BaseModel):
    """A line the user has added in the editor but not saved."""

    key: NewLineKey
    text: Words
    style_line_id: LineId | None = None


class DraftLine(BaseModel):
    """How the user has changed one line of the resume so far."""

    line_id: LineId
    text: Words | None = None
    removed: bool = False
    added: list[DraftNewLine] = Field(default_factory=list, max_length=20)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: Annotated[str, StringConstraints(max_length=2000)]


class AssistRequest(BaseModel):
    """A message to the resume assistant, with the editor as the user sees it now."""

    resume_id: uuid.UUID
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    # The chat so far, oldest first. Kept by the browser; nothing is stored.
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    lines: list[DraftLine] = Field(default_factory=list, max_length=300)
    skills: list[Annotated[str, StringConstraints(max_length=60)]] = Field(
        default_factory=list, max_length=12
    )
    links: list[LinkEdit] = Field(default_factory=list, max_length=40)


class AssistEdit(BaseModel):
    """One edit the assistant made, for the editor to apply to its draft."""

    kind: Literal["change", "remove", "add_below", "add_skill", "set_link"]
    # The resume line it is about (changed, removed, or added under).
    line_id: str | None
    # A line the user added in the editor: the one changed or removed, or the one
    # the new line goes after.
    new_key: str | None
    # add_below: the line whose look the new line copies.
    style_line_id: str | None
    # set_link: the link given the address in `text`.
    link_id: str | None = None
    text: str
    # The words the line had before, for showing what changed.
    before: str | None
    section: str | None
    # Skills and numbers in `text` that nothing the user wrote or saved supports.
    # An edit with any is not applied until the user says so.
    unsupported: list[str]


class AssistReply(BaseModel):
    reply: str
    edits: list[AssistEdit]
