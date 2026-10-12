"""The two model calls behind a match score.

The model does judgement only: it reads the job and labels each skill
strong / partial / missing, pointing at an evidence item by id. It never
produces a number and never writes the evidence text itself; the score is
calculated in `modules/matches/scoring.py` and the evidence shown to the user
is looked up from their own profile by id, so it cannot be invented.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from backend.ai.llm_client import generate_structured
from backend.ai.prompts import load_prompt

EXTRACT_PROMPT_VERSION = 1
JUDGE_PROMPT_VERSION = 1
PROMPT_VERSIONS = f"extract_job.v{EXTRACT_PROMPT_VERSION}+judge_skills.v{JUDGE_PROMPT_VERSION}"

Verdict = Literal["strong", "partial", "missing"]


class ExtractedJob(BaseModel):
    role: str | None = None
    company: str | None = None
    min_years_experience: int | None = Field(default=None, ge=0, le=50)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)


class SkillJudgement(BaseModel):
    skill_id: str
    verdict: Verdict
    evidence_id: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    label: str
    text: str


async def extract_job(jd_text: str, *, user_api_key: str | None) -> ExtractedJob:
    result = await generate_structured(
        f"JOB DESCRIPTION:\n<<<\n{jd_text}\n>>>",
        ExtractedJob,
        user_api_key=user_api_key,
        system_instruction=load_prompt("extract_job", EXTRACT_PROMPT_VERSION),
    )
    assert isinstance(result, ExtractedJob)
    return result


async def judge_skills(
    skills: list[str], evidence: list[EvidenceItem], *, user_api_key: str | None
) -> dict[int, SkillJudgement]:
    """Returns judgements keyed by the skill's index in `skills`."""
    skill_lines = "\n".join(f"K{i + 1}: {name}" for i, name in enumerate(skills))
    evidence_lines = "\n\n".join(f"{item.id} [{item.label}]\n{item.text}" for item in evidence)
    result = await generate_structured(
        f"SKILLS:\n{skill_lines}\n\nEVIDENCE:\n<<<\n{evidence_lines}\n>>>",
        list[SkillJudgement],
        user_api_key=user_api_key,
        system_instruction=load_prompt("judge_skills", JUDGE_PROMPT_VERSION),
    )
    assert isinstance(result, list)

    by_index: dict[int, SkillJudgement] = {}
    for judgement in result:
        raw = judgement.skill_id.strip().upper().removeprefix("K")
        if raw.isdigit() and 1 <= int(raw) <= len(skills):
            by_index.setdefault(int(raw) - 1, judgement)
    return by_index
