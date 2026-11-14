"""Answers written by the model, on request, for a box nothing else could fill.

Each answer spends AI credits from the user's plan (`modules/credits`), taken
before the model is called and given back if the call fails.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai import answer_writer
from backend.core.exceptions import ValidationFailedError
from backend.modules.ai_calls import service as ai_calls
from backend.modules.credits import service as credits
from backend.modules.matches.local.catalog import find_skills
from backend.modules.pitch.composer import ranked_projects, skill_label, skills_in_job
from backend.modules.profiles import service as profiles_service
from backend.modules.profiles.schemas import ProfileRead
from backend.modules.resume_editor.assistant import profile_text

Mode = Literal["write", "improve"]

_NUMBER = re.compile(r"(?<![\w.])\d[\d,.]*[%+xkKmM]?")
_URL = re.compile(r"https?://\S+|www\.\S+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Usage:
    """AI credits left this month, and the plan's monthly allowance."""

    left: int
    limit: int


@dataclass(frozen=True)
class AiAnswer:
    text: str
    # Claims taken out because nothing the user wrote or saved supports them.
    removed: list[str]
    usage: Usage


# What the model is shown of a profile and a posting. A short prompt answers sooner
# and costs less; the answer only needs what this job is about.
_JOB_CHARS = 2500
_ITEM_CHARS = 450
_ITEMS = 3
_OTHER_SKILLS = 12


def focused_profile(profile: ProfileRead, job_text: str, question: str) -> str:
    """The parts of the profile that matter for this question and job: the skills
    the job names first, the most relevant projects, the latest roles. Each item is
    cut short. Claims are still checked against the whole profile."""
    wanted = skills_in_job(profile, f"{job_text}\n{question}")
    others = [
        label
        for skill in profile.skills
        if (label := skill_label(skill.name)) and label not in wanted
    ][:_OTHER_SKILLS]
    lines = [f"Name: {profile.full_name or ''}. Headline: {profile.headline or ''}"]
    if wanted:
        lines.append(f"Skills this job names: {', '.join(wanted)}")
    if others:
        lines.append(f"Other skills: {', '.join(others)}")
    roles = sorted(
        profile.experience, key=lambda r: (r.end or "9999-12", r.start or ""), reverse=True
    )
    for role in roles[:_ITEMS]:
        dates = f"{role.start or '?'} to {role.end or 'present'}"
        lines.append(
            f"Role: {role.title} at {role.company} ({dates}). {role.description[:_ITEM_CHARS]}"
        )
    for project in ranked_projects(profile, wanted, job_text)[:_ITEMS]:
        tech = f" Tech: {', '.join(project.tech[:8])}." if project.tech else ""
        lines.append(f"Project: {project.name}.{tech} {project.description[:_ITEM_CHARS]}")
    for school in profile.education[:2]:
        lines.append(f"Education: {school.degree} {school.field or ''} at {school.school}")
    links = [link for link in (profile.links.portfolio, profile.links.github) if link]
    if links:
        lines.append(f"Links: {', '.join(links)}")
    return "\n".join(line.strip() for line in lines)


async def usage(db: AsyncSession, *, user_id: uuid.UUID) -> Usage:
    found = await credits.usage(db, user_id=user_id)
    return Usage(left=found.left, limit=found.limit)


def unsupported(text: str, sources: str) -> list[str]:
    """Numbers, links and skills in `text` found nowhere in `sources`."""
    lowered = sources.lower()
    known_skills = {mention.skill.name.lower() for mention in find_skills(sources)}
    flags: list[str] = []
    for number in _NUMBER.findall(text):
        core = number.rstrip("%+xkKmM.,")
        if core and not re.search(rf"(?<![\d.]){re.escape(core)}(?![\d])", lowered):
            flags.append(number)
    for match in _URL.finditer(text):
        address = match.group(0).rstrip(".,)")
        if address.lower() not in lowered:
            flags.append(address)
    for mention in find_skills(text):
        written = text[mention.start : mention.end]
        if mention.skill.name.lower() not in known_skills and written.lower() not in lowered:
            flags.append(written)
    return list(dict.fromkeys(flags))


def keep_supported(text: str, sources: str) -> tuple[str, list[str]]:
    """The text without any sentence making a claim `sources` cannot back."""
    kept: list[str] = []
    removed: list[str] = []
    for sentence in _SENTENCE.split(text.strip()):
        flags = unsupported(sentence, sources)
        if flags:
            removed.extend(flags)
        elif sentence:
            kept.append(sentence)
    return " ".join(kept), list(dict.fromkeys(removed))


def _prompt(
    *,
    mode: Mode,
    question: str,
    context: str,
    company: str | None,
    role: str | None,
    job_text: str,
    profile: str,
    current: str,
    limit: int,
) -> str:
    parts = [
        f"MODE: {mode}",
        f"LIMIT: {limit} characters",
        f"QUESTION:\n<<<\n{question}\n{context}\n>>>",
        f"JOB:\n<<<\nCompany: {company or 'unknown'}\nRole: {role or 'unknown'}\n"
        f"{job_text[:_JOB_CHARS]}\n>>>",
        f"PROFILE:\n<<<\n{profile}\n>>>",
    ]
    if mode == "improve":
        parts.append(f"CURRENT ANSWER:\n<<<\n{current}\n>>>")
    return "\n\n".join(parts)


async def write_answer(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    mode: Mode,
    question: str,
    context: str,
    company: str | None,
    role: str | None,
    job_text: str,
    current: str,
    limit: int,
) -> AiAnswer:
    """Writes (or improves) the answer for one box and checks every claim in it
    against the user's own data. Spends one AI credit; a failure gives it back
    (the request's transaction rolls back)."""
    if mode == "improve" and not current.strip():
        raise ValidationFailedError("Type something in the box first, then improve it.")
    balance = await credits.spend(db, user_id=user_id, action="ai_answer")

    full_profile = await profiles_service.get_profile(db, user_id=user_id)
    profile = profile_text(full_profile)
    prompt = _prompt(
        mode=mode,
        question=question,
        context=context,
        company=company,
        role=role,
        job_text=job_text,
        profile=focused_profile(full_profile, job_text, question),
        current=current,
        limit=limit,
    )
    with ai_calls.called_by(user_id, "extension"):
        written = await answer_writer.write_answer(prompt)

    sources = "\n".join([profile, current, question, context, company or "", role or "", job_text])
    text, removed = keep_supported(written.answer, sources)
    if not text:
        raise ValidationFailedError(
            "Your profile does not have what this question asks, so AI could not answer it"
            " truthfully. Please type your answer."
        )
    return AiAnswer(
        text=text[:limit], removed=removed, usage=Usage(left=balance.left, limit=balance.limit)
    )
