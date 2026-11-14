from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.ext_events import repository as events_repo
from backend.modules.ext_events.schemas import ExtEventsWrite
from backend.modules.ext_installs import service as installs_service
from backend.modules.extension import service
from backend.modules.extension.schemas import AutofillData, ExtensionConnected, ExtensionStatus
from backend.modules.matches import scoring
from backend.modules.pitch import ai_answers
from backend.modules.pitch import service as pitch_service
from backend.modules.pitch.schemas import (
    AiAnswerRead,
    AiAnswerRequest,
    AiUsageRead,
    PitchAnswerRead,
    PitchAnswersRequest,
)
from backend.modules.profiles import service as profiles_service
from backend.modules.saved_answers import service as saved_answers_service
from backend.modules.saved_answers.matching import is_placeholder_key
from backend.modules.saved_answers.schemas import (
    LearnedAnswerRead,
    LearnedAnswersWrite,
    MatchQuestionsRequest,
    QuestionKey,
    QuestionMatchRead,
)
from backend.modules.users.dependencies import get_db_user, get_db_user_or_extension
from backend.modules.users.models import User

# Managing the connection is done from the dashboard only: those routes use
# `get_db_user`, which refuses a request signed with an extension key. Reading
# and writing the autofill data is the one thing here the extension itself may do.
router = APIRouter(prefix="/extension", tags=["extension"])


@router.post("/connect", response_model=ExtensionConnected, status_code=201)
async def connect_extension(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ExtensionConnected:
    token, row = await service.connect(db, user_id=user.id)
    return ExtensionConnected(token=token, connected_at=row.created_at)


@router.get("/status", response_model=ExtensionStatus)
async def read_extension_status(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ExtensionStatus:
    row = await service.get_connection(db, user_id=user.id)
    return ExtensionStatus(
        connected=row is not None,
        connected_at=row.created_at if row else None,
        last_used_at=row.last_used_at if row else None,
    )


@router.delete("/connection", status_code=204)
async def disconnect_extension(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.disconnect(db, user_id=user.id)


@router.get("/autofill", response_model=AutofillData)
async def read_autofill_data(
    user: User = Depends(get_db_user_or_extension), db: AsyncSession = Depends(get_db)
) -> AutofillData:
    profile = await profiles_service.get_profile(db, user_id=user.id)
    answers = await saved_answers_service.list_answers(db, user_id=user.id)
    years = scoring.years_of_experience(
        [(role.start, role.end) for role in profile.experience if role.start],
        datetime.now(UTC).date(),
    )
    return AutofillData(
        email=user.email,
        profile=profile,
        # Answers older versions saved under placeholder keys would fill every box.
        saved_answers={
            answer.question_key: answer.answer
            for answer in answers
            if not is_placeholder_key(answer.question_key)
        },
        years_of_experience=years,
    )


@router.post("/learned-answers", response_model=list[LearnedAnswerRead])
async def learn_answers(
    payload: LearnedAnswersWrite,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> list[LearnedAnswerRead]:
    """Remembers what the user typed into a form, for the next form that asks.
    Repeating a request changes nothing, so the extension may retry it.
    """
    learned = await saved_answers_service.learn_answers(
        db,
        user_id=user.id,
        answers=[(answer.question_key, answer.answer) for answer in payload.answers],
    )
    return [LearnedAnswerRead(question_key=key, previous=previous) for key, previous in learned]


@router.delete("/learned-answers/{question_key}", status_code=204)
async def forget_answer(
    question_key: QuestionKey,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> None:
    """The Undo for an answer that was new when it was learned."""
    await saved_answers_service.delete_answer(db, user_id=user.id, question_key=question_key)


@router.post("/answer-matches", response_model=list[QuestionMatchRead])
async def match_saved_answers(
    payload: MatchQuestionsRequest,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionMatchRead]:
    """Saved answers for a form's questions that are worded differently from
    before. Sent once per form, for every question no answer is stored under.
    """
    reused = await saved_answers_service.reuse_answers(
        db,
        user_id=user.id,
        questions=[(question.key, question.text) for question in payload.questions],
    )
    return [
        QuestionMatchRead(
            key=item.asked_key,
            answer=item.answer,
            matched_key=item.matched_key,
            matched_question=item.matched_question,
            confidence=item.confidence,
        )
        for item in reused
    ]


@router.post("/pitch-answers", response_model=list[PitchAnswerRead])
async def write_pitch_answers(
    payload: PitchAnswersRequest,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> list[PitchAnswerRead]:
    """Answers to a form's "Why this company?"-type questions, made for this job
    from the user's saved answers and profile. No model call: free and instant.
    """
    answers = await pitch_service.answer_pitch_questions(
        db,
        user_id=user.id,
        questions=[
            (question.key, question.text, question.context) for question in payload.questions
        ],
        company=payload.company,
        role=payload.role,
        job_text=payload.job_text,
    )
    return [
        PitchAnswerRead(
            key=answer.key,
            kind=answer.kind,
            text=answer.text,
            source=answer.source,
            uses=answer.uses,
            company=answer.company,
        )
        for answer in answers
    ]


@router.get("/ai-answers/usage", response_model=AiUsageRead)
async def read_ai_answer_usage(
    user: User = Depends(get_db_user_or_extension), db: AsyncSession = Depends(get_db)
) -> AiUsageRead:
    usage = await ai_answers.usage(db, user_id=user.id)
    return AiUsageRead(left=usage.left, limit=usage.limit)


@router.post("/ai-answers", response_model=AiAnswerRead)
async def write_ai_answer(
    payload: AiAnswerRequest,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> AiAnswerRead:
    """Writes or improves one answer with the model, when the user asks. Spends one
    AI credit; every claim is checked against the user's own data."""
    answer = await ai_answers.write_answer(
        db,
        user_id=user.id,
        mode=payload.mode,
        question=payload.question,
        context=payload.context,
        company=payload.company,
        role=payload.role,
        job_text=payload.job_text,
        current=payload.current,
        limit=payload.max_length,
    )
    return AiAnswerRead(
        text=answer.text,
        removed=answer.removed,
        usage=AiUsageRead(left=answer.usage.left, limit=answer.usage.limit),
    )


@router.post("/events", status_code=204)
async def record_events(
    payload: ExtEventsWrite,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Usage events from the extension, sent in batches. Each event carries the
    extension's own id for it, so a retried batch is stored once.
    """
    now = datetime.now(UTC)
    await events_repo.insert_events(
        db,
        user_id=user.id,
        events=[
            {
                "name": event.name,
                "host": event.host,
                "count": event.count,
                "client_id": event.id,
                "version": event.version,
                "session_id": event.session,
                "props": event.props,
                "created_at": event.happened_at(now) or now,
                "updated_at": now,
            }
            for event in payload.events
        ],
    )
    if payload.install is not None:
        await installs_service.link(db, payload.install, user.id)
