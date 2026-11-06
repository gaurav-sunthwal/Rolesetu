"""Domain field persistence, snapshots, and cached catalogs."""

import uuid
from typing import Any

from httpx import AsyncClient

from backend.ai.profile_understanding import ProfileUnderstanding
from backend.db.session import get_sessionmaker
from backend.modules.domain_catalogs import repository as catalog_repository
from backend.modules.domain_catalogs.service import load_fixture
from backend.modules.matches import service as match_service
from backend.modules.matches.local.domain_catalogs import field_keys_for_match
from backend.modules.matches.local.jd import parse_job
from backend.modules.matches.models import Job, Match
from backend.modules.profiles.field_detection import resolve_field
from backend.modules.profiles.field_snapshot import build_field_snapshot
from backend.modules.profiles.schemas import ProfileRead, ProfileWrite
from backend.tests.conftest import ClientFactory

HR_WRITE: dict[str, Any] = {
    "full_name": "Priya Nair",
    "headline": "HR Operations Intern",
    "links": {},
    "skills": [
        {"id": "s1", "name": "Employee onboarding"},
        {"id": "s2", "name": "Documentation"},
        {"id": "s3", "name": "HRIS"},
    ],
    "experience": [
        {
            "id": "e1",
            "title": "HR Operations Intern",
            "company": "PeopleFirst",
            "start": "2024-06",
            "end": None,
            "description": "Managed employee onboarding and HRIS records for 40 hires.",
        }
    ],
    "projects": [],
    "education": [{"id": "d1", "school": "Delhi University", "degree": "BBA", "field": "HR"}],
    "field_key": "hr",
    "scope_summary": "HR operations intern focused on onboarding and records.",
    "inferred_field_key": None,
}

HR_PROFILE = {
    **HR_WRITE,
    "location": None,
    "phone": None,
    "version": 1,
    "completeness": 80,
    "updated_at": None,
}

HR_JD = """HR Operations Executive
Requirements
- Recruitment and talent acquisition
- Employee onboarding and HRIS
- Payroll processing and statutory compliance
- Performance management
Nice to have
- Workday
"""


async def _seed_hr_catalog() -> None:
    fixture = load_fixture("hr")
    assert fixture is not None
    text, core = fixture
    async with get_sessionmaker()() as db:
        await catalog_repository.upsert(
            db,
            field_key="hr",
            source="fixture",
            catalog_text=text,
            core_skill_names=core,
        )
        await db.commit()


async def test_empty_profile_exposes_field_columns(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/profile/me")).json()
    assert body["field_key"] is None
    assert body["scope_summary"] is None
    assert body["inferred_field_key"] is None


async def test_field_columns_are_private(make_client: ClientFactory) -> None:
    alice, bob = make_client(), make_client()
    await alice.put("/api/v1/profile/me", json=HR_WRITE)
    assert (await bob.get("/api/v1/profile/me")).json()["field_key"] is None


def test_resolve_field_flags_title_mismatch() -> None:
    profile = ProfileWrite.model_validate(HR_WRITE)
    profile.field_key = None
    ai = ProfileUnderstanding(field="marketing", scope_summary="Marketing intern")
    key, _scope, inferred = resolve_field(profile, ai)
    assert key == "marketing"
    assert inferred == "hr"


async def test_hr_fixture_catalog_improves_jd_parse() -> None:
    await _seed_hr_catalog()
    fixture = load_fixture("hr")
    assert fixture is not None
    append = fixture[0]
    before = parse_job(HR_JD, ())
    after = parse_job(HR_JD, (), catalog_append=append)
    assert len(after.requirements) >= len(before.requirements)


async def test_field_snapshot_for_hr_profile() -> None:
    await _seed_hr_catalog()
    profile = ProfileRead.model_validate(HR_PROFILE)
    async with get_sessionmaker()() as db:
        snapshot = await build_field_snapshot(db, user_id=uuid.uuid4(), profile=profile)
    assert snapshot.catalog_status == "ready"
    assert snapshot.field_label == "HR and recruiting"
    assert any(item.verdict == "strong" for item in snapshot.skills)


async def test_software_snapshot_uses_hand_core() -> None:
    profile = ProfileRead.model_validate(
        {
            **HR_PROFILE,
            "field_key": "software",
            "headline": "Full Stack Developer",
            "skills": [{"id": "s1", "name": "JavaScript"}],
            "experience": [
                {
                    "id": "e1",
                    "title": "Full Stack Developer Intern",
                    "company": "Acme",
                    "start": "2024-01",
                    "end": None,
                    "description": "Built APIs with JavaScript.",
                }
            ],
        }
    )
    async with get_sessionmaker()() as db:
        snapshot = await build_field_snapshot(db, user_id=uuid.uuid4(), profile=profile)
    assert snapshot.catalog_status == "ready"
    assert any(s.name == "Software development" and s.verdict == "strong" for s in snapshot.skills)


def test_an_hr_internship_is_a_stretch_for_someone_aiming_at_hr() -> None:
    """Exact skill names are missing, but the person is heading into this field
    and the posting is an internship, so the score is not zero.
    """
    profile = ProfileRead.model_validate(
        {
            **HR_PROFILE,
            "headline": "Aspiring HR Operations Professional",
            "skills": [
                {"id": "s1", "name": "HR Operations Fundamentals"},
                {"id": "s2", "name": "Documentation Management"},
            ],
            "experience": [
                {
                    "id": "e1",
                    "title": "Cyber Security Intern",
                    "company": "CPR",
                    "start": "2026-10",
                    "end": None,
                    "description": "Administrative assistance for departmental supervisors.",
                }
            ],
        }
    )
    text = """Human Resources Intern
    Recruitment and talent acquisition. Interview coordination. Employee onboarding.
    Prior HR experience is not mandatory.
    """
    job = Job(role="Human Resources Intern", jd_text=text, url=None, company=None, job_json=None)
    match = Match(job=job, profile_version=1)
    match_service.score_without_model(job, match, profile, None, "")
    assert match.score == 40
    assert "Recruitment" in match.gaps
    assert "entry-level" in (match.experience or {})["assessment"]["background"]


def test_a_job_outside_the_persons_field_does_not_request_that_catalog() -> None:
    profile = ProfileRead.model_validate(HR_PROFILE)
    keys = field_keys_for_match(profile, "Mechanical Design Engineer")
    assert "hr" in keys
    assert "mechanical" not in keys


async def test_match_uses_domain_catalog() -> None:
    await _seed_hr_catalog()
    fixture = load_fixture("hr")
    assert fixture is not None
    text = fixture[0]
    profile = ProfileRead.model_validate(HR_PROFILE)
    job = Job(role="HR Operations Executive", jd_text=HR_JD, url=None, company=None, job_json=None)
    match = Match(job=job, profile_version=1)
    match_service.score_without_model(job, match, profile, None, text)
    names = {item["name"] for item in match.skill_results}
    assert names  # parsed at least one requirement from the HR posting
