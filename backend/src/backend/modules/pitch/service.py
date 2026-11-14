import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.matches import scoring
from backend.modules.pitch.composer import (
    JobContext,
    PitchKind,
    addressee,
    company_in,
    compose,
    fill_template,
    is_template,
    pitch_kind,
)
from backend.modules.profiles import service as profiles_service
from backend.modules.saved_answers import repository as answers_repository
from backend.modules.saved_answers.matching import match_questions


def _says_little(label: str) -> bool:
    """A label that names a box rather than asks something: "Your message", "Note"."""
    return "?" not in label and len(label.split()) <= 4


def _kind_of_key(key: str) -> PitchKind | None:
    if key == "why_this_role":
        return "why_company"
    return pitch_kind(key.removeprefix("q_").replace("_", " "))


@dataclass(frozen=True)
class PitchAnswer:
    key: str
    kind: PitchKind
    text: str
    source: Literal["your_answer", "profile"]
    uses: list[str]
    company: str | None


async def answer_pitch_questions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    questions: list[tuple[str, str, str]],
    company: str | None,
    role: str | None,
    job_text: str,
) -> list[PitchAnswer]:
    """Answers for the written questions among `questions` (key, words, the words
    around the box), made for
    this company. The user's own saved answer comes first, with this company's
    names put in; without one, the answer is written from the profile.
    Questions that are not pitch questions are left out.
    """
    # A box labelled only "Your message" is read by the pop-up it sits in. A box with
    # a question of its own ("Do you require visa sponsorship?") is that question,
    # whatever the pop-up around it is for.
    asked = [
        (key, text, context, kind)
        for key, text, context in questions
        if (kind := pitch_kind(text) or (pitch_kind(context) if _says_little(text) else None))
    ]
    if not asked:
        return []

    saved = await answers_repository.list_for_user(db, user_id)
    rows = {row.question_key: row.answer for row in saved}
    templates = {key: answer for key, answer in rows.items() if is_template(answer)}
    similar = (
        match_questions([text for _, text, _, _ in asked], list(templates)) if templates else []
    )
    # A "why this company" answer serves every "why this company" question, however
    # each one is worded: the saved question's own words say which kind it was.
    by_kind: dict[PitchKind, str] = {}
    for row in sorted(saved, key=lambda row: row.updated_at):  # the latest of each kind wins
        if row.question_key in templates and (kind := _kind_of_key(row.question_key)):
            by_kind[kind] = row.answer

    profile = await profiles_service.get_profile(db, user_id=user_id)
    years = scoring.years_of_experience(
        [(job.start, job.end) for job in profile.experience if job.start],
        datetime.now(UTC).date(),
    )

    answers: list[PitchAnswer] = []
    for index, (key, text, context, kind) in enumerate(asked):
        named = company or company_in(context) or company_in(text)
        # Without a role from the page, the headline still reads as one
        # ("as a Full Stack Developer").
        job = JobContext(
            company=named,
            role=role or profile.headline,
            text=job_text,
            founder=addressee(text) or addressee(context),
        )
        own = templates.get(key)
        if own is None and similar and (match := similar[index]) is not None:
            own = templates[match.key]
        if own is None:
            own = by_kind.get(kind)
        if own is not None:
            answers.append(
                PitchAnswer(key, kind, fill_template(own, job), "your_answer", [], named)
            )
            continue
        # Written from the profile, a role is only named when the page names one.
        composed = compose(kind, profile, replace(job, role=role), years=years)
        answers.append(PitchAnswer(key, kind, composed.text, "profile", composed.uses, named))
    return answers
