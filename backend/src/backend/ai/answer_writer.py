"""The model call that writes, or improves, one answer on an application form.

The model only proposes text. Code checks it afterwards (`modules/pitch/ai_answers.py`)
and removes any sentence naming a skill, number or link the user's own data does not
hold, so a made-up claim never reaches the form.
"""

from pydantic import BaseModel

from backend.ai.llm_client import generate_structured
from backend.ai.prompts import load_prompt
from backend.core.config import get_settings

PROMPT_VERSION = 1
PROMPT_NAME = f"write_answer.v{PROMPT_VERSION}"
# Generate and Improve are one kind of call, so they share one name in the call log.
PURPOSE = "form-answer"
# Someone is waiting with the box focused: a fast model answers in about 2s, so one
# that has not answered in 8s is overloaded, and the next one is tried.
TIMEOUT_SECONDS = 8.0


class WrittenAnswer(BaseModel):
    answer: str


async def write_answer(context: str) -> WrittenAnswer:
    result = await generate_structured(
        context,
        WrittenAnswer,
        purpose=PURPOSE,
        system_instruction=load_prompt("write_answer", PROMPT_VERSION),
        timeout_seconds=TIMEOUT_SECONDS,
        models=get_settings().fast_llm_models,
        thinking=False,
    )
    assert isinstance(result, WrittenAnswer)
    return result
