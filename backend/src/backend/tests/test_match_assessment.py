"""The checks that sit on top of skills: the job's field against the person's,
licences and degrees a job requires, years in the field, proof over claims,
and when a job is handed to the model. None of these touch the database.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.ai import matching
from backend.ai.matching import ExtractedJob, SkillJudgement
from backend.core.exceptions import ValidationFailedError
from backend.evals import matching as match_eval
from backend.evals.match_cases import JOBS, PROFILES
from backend.modules.matches import scoring, service
from backend.modules.matches.job_key import job_key
from backend.modules.matches.local import fields
from backend.modules.matches.local.engine import score_locally
from backend.modules.matches.local.experience import read_experience
from backend.modules.matches.local.must_haves import find_must_haves
from backend.modules.matches.models import Job, Match
from backend.modules.matches.schemas import SkillResult
from backend.modules.profiles.schemas import ProfileRead
from backend.modules.tailoring.keywords import suggest_headline


def person(key: str, **changes: Any) -> ProfileRead:
    return ProfileRead.model_validate({**PROFILES[key], **changes})


def new_match(job_key: str) -> tuple[Job, Match]:
    role, text = JOBS[job_key]
    job = Job(role=role, jd_text=text, url=None, company=None, job_json=None)
    return job, Match(job=job, profile_version=1)


# --- fields ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "field"),
    [
        ("Electrical Design Manager", "electrical"),
        ("Senior Technical Manager – Data & AI Leadership", "data"),
        ("Mechanical Design Engineer", "mechanical"),
        ("Marketing Data Analyst", "marketing"),
        ("Data Center Electrical Engineer", "electrical"),
        ("Account Executive", "sales"),
        ("Senior Accountant", "finance"),
        ("Frontend Developer", "software"),
        ("Project Manager", None),
    ],
)
def test_a_title_names_its_field(title: str, field: str | None) -> None:
    found = fields.field_of(title)
    assert (found.key if found else None) == field


def test_a_job_in_another_line_of_work_is_called_out() -> None:
    fit = fields.compare(fields.field_of("Electrical Design Manager"), ["data"])
    assert fit.status == "different"
    assert "electrical engineering" in fit.summary and "data and analytics" in fit.summary


def test_close_fields_are_related_and_unknown_titles_decide_nothing() -> None:
    assert fields.compare(fields.field_of("Backend Engineer"), ["data"]).status == "related"
    assert fields.compare(fields.field_of("Project Manager"), ["data"]).status == "unknown"
    assert fields.compare(fields.field_of("Data Engineer"), []).status == "unknown"


def test_a_person_with_no_roles_is_placed_by_what_they_studied() -> None:
    assert fields.fields_of_person([], None, ["Computer Science B.Tech"]) == ["software"]


# --- must-haves --------------------------------------------------------------


def test_a_required_licence_and_degree_are_checked_against_the_profile() -> None:
    text = JOBS["electrical_design_manager"][1]
    lacking = {m.name: m.held for m in find_must_haves(text, person("data_architect"))}
    holding = {m.name: m.held for m in find_must_haves(text, person("electrical_engineer"))}
    assert lacking == {
        "Degree in Electrical Engineering": False,
        "Professional Engineer (PE) license": False,
    }
    assert all(holding.values()) and holding.keys() == lacking.keys()


def test_preferred_and_flexible_qualifications_are_not_must_haves() -> None:
    text = (
        "A PE license is a plus.\n"
        "Bachelor's degree in Computer Science or a related field.\n"
        "CA or CPA preferred."
    )
    assert find_must_haves(text, person("data_architect")) == []


def test_abbreviated_degrees_are_read() -> None:
    text = "- B.Tech or B.E. in Mechanical Engineering."
    (must,) = find_must_haves(text, person("mechanical_engineer"))
    assert must.name == "Degree in Mechanical Engineering" and must.held


# --- scoring rules -------------------------------------------------------------


def test_the_lowest_limit_wins_and_only_limits_that_bit_are_reported() -> None:
    caps = [
        scoring.Cap("field", 35, "field"),
        scoring.Cap("thin", 60, "thin"),
        scoring.Cap("experience", 90, "years"),
    ]
    score, applied = scoring.apply_caps(80, caps)
    assert score == 35
    assert [cap.kind for cap in applied] == ["field", "thin"]


def test_a_skill_in_the_title_counts_double() -> None:
    plain = scoring.compute_score([scoring.Judged(True, "strong"), scoring.Judged(True, "missing")])
    core = scoring.compute_score(
        [scoring.Judged(True, "strong", weight=2.0), scoring.Judged(True, "missing")]
    )
    assert plain == 50 and core == 67


def test_years_in_another_field_do_not_count() -> None:
    _, result = scoring.check_experience(
        90,
        required_min=5,
        source="stated",
        candidate_years=0,
        field_label="electrical engineering",
        total_years=10.9,
    )
    assert result.status == "well_short"
    assert "no work in electrical engineering yet" in result.summary
    assert result.total_years == 10.9


# --- proof over claims -----------------------------------------------------------


def test_a_skill_last_used_long_ago_is_only_partial() -> None:
    profile = person(
        "backend_dev",
        experience=[
            {
                "id": "e1",
                "title": "Backend Engineer",
                "company": "Old Co",
                "start": "2010-01",
                "end": "2015-06",
                "description": "Built services with Django and PostgreSQL.",
            }
        ],
    )
    result = score_locally(profile, "Requirements: Django and PostgreSQL.")
    found = {item.name: item for item in result.judgements}
    assert found["Django"].verdict == "partial"
    assert "ended in 2015" in found["Django"].reason


# --- where a job is scored: always here, never by the model ---------------------------


def test_a_job_outside_software_in_the_persons_field_is_scored_here() -> None:
    job, match = new_match("electrical_design_manager")
    service.score_without_model(job, match, person("electrical_engineer"), None)
    assert match.score is not None and match.score >= 65
    verdicts = {item["name"]: item["verdict"] for item in match.skill_results}
    assert verdicts["Power distribution"] == "strong"
    assert verdicts["Arc flash studies"] == "strong"


def test_a_job_in_a_line_of_work_the_person_never_had_is_held_low() -> None:
    """The reported case: a data architect was shown 100% for this role."""
    job, match = new_match("electrical_design_manager")
    service.score_without_model(job, match, person("data_architect"), None)
    match.id, match.created_at = uuid.uuid4(), datetime.now(UTC)
    shown = service.to_read(match, datetime.now(UTC))

    assert shown.score is not None and shown.score <= scoring.FIELD_CAP
    assert shown.summary is not None and "electrical engineering role" in shown.summary
    names = {item.name: item.verdict for item in shown.skill_results}
    assert names["Professional Engineer (PE) license"] == "missing"
    assert names["Degree in Electrical Engineering"] == "missing"
    assert names["Power distribution"] == "missing"
    assert names["Data analysis"] == "strong"


def test_a_related_field_gets_a_full_read() -> None:
    job, match = new_match("electrical_design_manager")
    service.score_without_model(job, match, person("mechanical_engineer"), None)
    assert match.score is not None and match.status == "completed"


def test_a_software_job_is_scored_here() -> None:
    job, match = new_match("backend_engineer")
    service.score_without_model(job, match, person("backend_dev"), None)
    assert match.score is not None and match.score >= 65


def test_text_that_is_not_a_job_is_turned_away_without_a_model() -> None:
    job = Job(role=None, jd_text="We love coffee and long walks. " * 10, url=None, job_json=None)
    with pytest.raises(ValidationFailedError):
        service.score_without_model(job, Match(job=job, profile_version=1), person("nurse"), None)


def test_the_reported_job_cannot_score_high_whatever_the_skills_say() -> None:
    """A data architect was shown 100% for an Electrical Design Manager role."""
    job, match = new_match("electrical_design_manager")
    every_skill_strong = [
        SkillResult(name=name, required=True, verdict="strong")
        for name in ("Data analysis", "Power distribution", "AutoCAD", "Revit", "NEC")
    ]
    service._finish(  # noqa: SLF001
        job,
        match,
        person("data_architect"),
        every_skill_strong,
        asked=read_experience(job.jd_text, job.role),
        engine_version="test",
    )
    match.id, match.created_at = uuid.uuid4(), datetime.now(UTC)
    shown = service.to_read(match, datetime.now(UTC))

    assert shown.score is not None and shown.score <= scoring.FIELD_CAP
    assert shown.field_fit is not None and shown.field_fit.status == "different"
    assert {limit.kind for limit in shown.limits} >= {"field", "must_have"}
    assert shown.score_cap == scoring.FIELD_CAP
    assert "Professional Engineer (PE) license" in shown.gaps
    assert shown.experience is not None and shown.experience.status == "well_short"


# --- the reason shown with every score ------------------------------------------------


def test_the_reason_is_the_limit_that_held_the_score_lowest() -> None:
    job, match = new_match("electrical_design_manager")
    service._finish(  # noqa: SLF001
        job,
        match,
        person("data_architect"),
        [SkillResult(name=f"S{n}", required=True, verdict="strong") for n in range(4)],
        asked=read_experience(job.jd_text, job.role),
        engine_version="test",
    )
    match.id, match.created_at = uuid.uuid4(), datetime.now(UTC)
    summary = service.to_read(match, datetime.now(UTC)).summary
    assert summary is not None and summary.startswith("This is an electrical engineering role")


def test_without_limits_the_reason_counts_the_required_skills() -> None:
    job, match = new_match("backend_engineer")
    service.score_without_model(job, match, person("frontend_dev"), None)
    match.id, match.created_at = uuid.uuid4(), datetime.now(UTC)
    summary = service.to_read(match, datetime.now(UTC)).summary
    assert summary is not None and summary.startswith("Your profile shows ")
    assert "Missing: " in summary


# --- reading a job once ----------------------------------------------------------------


async def test_a_saved_reading_of_the_job_saves_the_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[object] = []

    async def fake_model(prompt: str, schema: object, **_: object) -> object:
        asked.append(schema)
        return [SkillJudgement(skill_id="K1", verdict="strong", evidence_id="E1", reason="Used")]

    monkeypatch.setattr(matching, "generate_structured", fake_model)
    job, match = new_match("mechanical_design_engineer")
    # A skill the dictionary does not know, so the model is asked to judge it.
    known = ExtractedJob(role="Mechanical Design Engineer", required_skills=["Gearbox packaging"])
    await service.score_with_model(
        job, match, person("mechanical_engineer"), user_api_key=None, known=known
    )
    assert asked == [list[SkillJudgement]]  # judged only; the job was not read again
    assert match.status == "completed"
    assert job.job_json is not None
    assert job.job_json["extract_version"] == matching.EXTRACT_PROMPT_VERSION


def test_only_a_reading_from_the_current_prompt_is_reused() -> None:
    saved = {"required_skills": ["SolidWorks"], "extract_version": matching.EXTRACT_PROMPT_VERSION}
    assert service._saved_extraction(saved) is not None  # noqa: SLF001
    assert service._saved_extraction({**saved, "extract_version": 0}) is None  # noqa: SLF001
    # A local reading has no version: its skills come from the dictionary.
    assert service._saved_extraction({"required_skills": ["React"]}) is None  # noqa: SLF001


@pytest.mark.parametrize(
    ("url", "key"),
    [
        ("https://www.linkedin.com/jobs/view/4460038564/", "linkedin:4460038564"),
        (
            "https://www.linkedin.com/jobs/view/electrical-design-manager-at-x-4460038564?trk=a",
            "linkedin:4460038564",
        ),
        (
            "https://www.linkedin.com/jobs/search/?currentJobId=4460038564&f=1",
            "linkedin:4460038564",
        ),
        ("https://in.indeed.com/viewjob?jk=9C3E1A2B4D5F6A7B", "indeed:9c3e1a2b4d5f6a7b"),
        ("https://job-boards.greenhouse.io/acme/jobs/7123456", "greenhouse:7123456"),
        # No id we can trust: never guessed, so one job's result never reaches another.
        ("https://acme.com/careers/123", None),
        (None, None),
    ],
)
def test_a_job_is_known_by_the_id_in_its_link(url: str | None, key: str | None) -> None:
    assert job_key(url) == key


async def test_each_skill_is_judged_by_the_cheapest_thing_that_can(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []

    async def fake_model(prompt: str, schema: object, **_: object) -> object:
        sent.append(prompt)
        return [SkillJudgement(skill_id="K1", verdict="missing", reason="Not shown")]

    monkeypatch.setattr(matching, "generate_structured", fake_model)
    job, match = new_match("electrical_design_manager")
    known = ExtractedJob(
        role="Electrical Design Manager",
        required_skills=["Python", "Busway sizing", "Grounding grid design"],
    )
    remembered = {
        "busway sizing": SkillResult(name="Busway sizing", required=False, verdict="missing")
    }
    await service.score_with_model(
        job,
        match,
        person("data_architect"),
        user_api_key=None,
        known=known,
        remembered=remembered,
    )
    # Python: the dictionary. Busway sizing: judged on an earlier job.
    # Only the one skill nothing knew went to the model.
    assert len(sent) == 1
    asked_about = sent[0].split("EVIDENCE:")[0]
    assert "K1: Grounding grid design" in asked_about and "Python" not in asked_about
    verdicts = {item["name"]: item["verdict"] for item in match.skill_results}
    assert verdicts["Python"] == "strong"
    assert verdicts["Busway sizing"] == "missing"


async def test_a_job_whose_skills_are_all_known_costs_no_judging_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_model(*_: object, **__: object) -> object:
        raise AssertionError("no model call was needed")

    monkeypatch.setattr(matching, "generate_structured", no_model)
    job, match = new_match("data_engineer")
    known = ExtractedJob(
        role="Senior Data Engineer", required_skills=["SQL", "Python", "Snowflake"]
    )
    await service.score_with_model(
        job, match, person("data_architect"), user_api_key=None, known=known
    )
    assert match.status == "completed" and match.score is not None


# --- tailoring stays truthful ------------------------------------------------------------


def test_no_job_title_from_another_field_is_suggested_for_the_resume() -> None:
    assert suggest_headline("FULL STACK DEVELOPER", "Fresher Mechanical Engineer") is None
    assert suggest_headline("Frontend Engineer", "Senior Frontend Developer") is not None


# --- the eval, as a guard ----------------------------------------------------------


async def test_no_unrelated_job_can_be_shown_as_a_good_fit() -> None:
    outcomes = [await match_eval.run_pair(p, j, use_model=False) for p in PROFILES for j in JOBS]
    unrelated = [o for o in outcomes if o.expect == "low"]
    assert all(o.score is None or o.score < match_eval.LOW for o in unrelated)
    # Every job in the person's own field is scored here, and scored as a fit.
    own_field = [o for o in outcomes if o.expect == "high"]
    assert all(o.score is not None and o.score >= match_eval.HIGH for o in own_field)


# --- answering first, saving after ---------------------------------------------------


async def test_a_job_scored_here_is_answered_then_really_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The save is handed to the response's background tasks. It must be an async
    callable, or the task runner calls it in a thread and drops the save unrun
    (which once left every new check unsaved: "That job check no longer exists").
    """
    from starlette.background import BackgroundTask

    from backend.modules.matches import repository
    from backend.modules.matches.schemas import MatchCreate
    from backend.modules.profiles import service as profiles_service

    async def nothing_saved(*_: object, **__: object) -> None:
        return None

    async def no_checks_yet(*_: object, **__: object) -> int:
        return 0

    async def the_profile(*_: object, **__: object) -> ProfileRead:
        return person("backend_dev")

    saved: list[uuid.UUID] = []

    async def record_save(job: Job, match: Match) -> None:
        saved.append(match.id)

    monkeypatch.setattr(repository, "find_saved_result", nothing_saved)
    monkeypatch.setattr(repository, "count_since", no_checks_yet)
    monkeypatch.setattr(profiles_service, "get_profile", the_profile)
    monkeypatch.setattr(service, "_save_in_background", record_save)

    started = await service.start_match(
        None,  # type: ignore[arg-type]  # every database call above is replaced
        user_id=uuid.uuid4(),
        payload=MatchCreate(jd_text=JOBS["backend_engineer"][1], role="Senior Backend Engineer"),
    )
    assert started.match.status == "completed" and not started.needs_model
    assert started.save is not None

    await BackgroundTask(started.save)()
    assert saved == [started.match.id]
