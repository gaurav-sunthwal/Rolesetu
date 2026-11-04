"""The model call behind the resume editor's assistant.

The model only proposes edits to lines it is shown, by id. It never touches the
file: the editor makes the edits, code checks every id, and a separate check
(`modules/resume_editor/assistant.py`) flags any skill or number the person's
own words and data do not support.
"""

from typing import Literal

from pydantic import BaseModel, Field

from backend.ai.llm_client import generate_structured
from backend.ai.prompts import load_prompt

PROMPT_VERSION = 2
PROMPT_NAME = f"edit_resume.v{PROMPT_VERSION}"


class ProposedEdit(BaseModel):
    action: Literal["change", "remove", "add_below", "add_skill", "set_link"]
    line: str = ""
    style_like: str = ""
    text: str = ""


class AssistantAnswer(BaseModel):
    reply: str
    edits: list[ProposedEdit] = Field(default_factory=list)


async def propose_edits(context: str, *, user_api_key: str | None) -> AssistantAnswer:
    result = await generate_structured(
        context,
        AssistantAnswer,
        purpose="resume-assistant",
        user_api_key=user_api_key,
        system_instruction=load_prompt("edit_resume", PROMPT_VERSION),
    )
    assert isinstance(result, AssistantAnswer)
    return result
