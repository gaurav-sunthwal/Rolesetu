"""AI-powered understanding of a candidate's profile, role, field, scope, and skills.

Runs at profile creation / resume upload time so that the user's role context,
categorized skills, and chunked evidence are established upfront. Match scoring
can then run fast, local, and explainable without needing an LLM call per check.
"""

import logging

from pydantic import BaseModel, Field

from backend.ai.llm_client import generate_structured
from backend.ai.prompts import load_prompt

logger = logging.getLogger(__name__)

PROMPT_VERSION = 1


class CategorizedSkills(BaseModel):
    hr_administrative: list[str] = Field(default_factory=list)
    organisational: list[str] = Field(default_factory=list)
    interpersonal: list[str] = Field(default_factory=list)
    analytical: list[str] = Field(default_factory=list)
    professional: list[str] = Field(default_factory=list)
    technical_software: list[str] = Field(default_factory=list)


class ProfileUnderstanding(BaseModel):
    headline: str | None = None
    field: str = "general"
    scope_summary: str = ""
    categorized_skills: CategorizedSkills = Field(default_factory=CategorizedSkills)
    skills: list[str] = Field(default_factory=list)
    scope_chunks: list[str] = Field(default_factory=list)


async def understand_profile(
    resume_text: str, *, user_api_key: str | None = None
) -> ProfileUnderstanding | None:
    """Extracts role, field context, categorized skills, and chunked scope from resume text."""
    if not resume_text.strip():
        return None
    try:
        result = await generate_structured(
            resume_text[:12000],
            ProfileUnderstanding,
            purpose="profile-understanding",
            user_api_key=user_api_key,
            system_instruction=load_prompt("understand_profile", PROMPT_VERSION),
            timeout_seconds=20.0,
        )
        assert isinstance(result, ProfileUnderstanding)
        return result
    except Exception as exc:
        logger.warning("AI profile understanding was not available or failed: %s", exc)
        return None
