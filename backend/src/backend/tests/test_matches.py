from typing import Any

import pytest
from httpx import AsyncClient

from backend.ai import matching
from backend.ai.matching import ExtractedJob, SkillJudgement
from backend.core.config import get_settings
from backend.tests.conftest import ClientFactory

BASE = "/api/v1/matches"
JD = (
    "We are hiring a Frontend Engineer with 3+ years of experience. "
    "You must know React and Docker. GraphQL is a plus. " + "You will build product features. " * 8
)
PROFILE: dict[str, Any] = {
    "full_name": "Asha Rao",
    "skills": [{"id": "s1", "name": "GraphQL", "level": "intermediate"}],
    "experience": [
        {
            "id": "e1",
            "title": "Engineer",
            "company": "Acme",
            "start": "2020-01",
            "end": "2025-12",
            "description": "Built the admin app in React.",
        }
    ],
}


class FakeModel:
    """Stands in for Gemini. Evidence ids follow build_evidence order:
    E1 is the Acme job, E2 is the listed GraphQL skill.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.judgements = [
            SkillJudgement(
                skill_id="K1", verdict="strong", evidence_id="E1", reason="Used at Acme"
            ),
            SkillJudgement(skill_id="K2", verdict="missing", evidence_id=None, reason="Not shown"),
            SkillJudgement(
                skill_id="K3", verdict="partial", evidence_id="E2", reason="Listed only"
            ),
        ]

    async def __call__(self, prompt, response_schema, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if response_schema is ExtractedJob:
            return ExtractedJob(
                role="Frontend Engineer",
                company="Acme Labs",
                min_years_experience=3,
                required_skills=["React", "Docker"],
                nice_to_have_skills=["GraphQL"],
            )
        return self.judgements


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    fake = FakeModel()
    monkeypatch.setattr(matching, "generate_structured", fake)
    monkeypatch.setattr(get_settings(), "match_engine", "llm")
    return fake


async def test_needs_a_profile_first(client: AsyncClient, model: FakeModel) -> None:
    response = await client.post(BASE, json={"jd_text": JD})
    assert response.status_code == 422
    assert "profile" in response.json()["detail"]
    assert model.calls == 0


async def test_scores_a_job_and_explains_it(client: AsyncClient, model: FakeModel) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    started = await client.post(BASE, json={"jd_text": JD})
    assert started.status_code == 202

    body = (await client.get(f"{BASE}/{started.json()['id']}")).json()
    assert body["status"] == "completed"
    # React strong 2/2, Docker missing 0/2, GraphQL partial 0.5/1 -> 2.5 of 5
    assert body["score"] == 50
    assert body["seniority_note"] is None
    assert body["gaps"] == ["Docker"]
    assert body["role"] == "Frontend Engineer" and body["company"] == "Acme Labs"

    react = body["skill_results"][0]
    assert react["verdict"] == "strong"
    assert react["evidence_label"] == "Engineer at Acme"
    assert "admin app in React" in react["evidence_text"]


async def test_verdict_without_real_evidence_becomes_missing(
    client: AsyncClient, model: FakeModel
) -> None:
    model.judgements[0] = SkillJudgement(
        skill_id="K1", verdict="strong", evidence_id="E99", reason="Made up"
    )
    await client.put("/api/v1/profile/me", json=PROFILE)
    started = await client.post(BASE, json={"jd_text": JD})
    body = (await client.get(f"{BASE}/{started.json()['id']}")).json()

    react = body["skill_results"][0]
    assert react["verdict"] == "missing" and react["evidence_text"] is None
    assert "React" in body["gaps"]


async def test_seniority_cap_is_applied_and_explained(
    client: AsyncClient, model: FakeModel
) -> None:
    model.judgements[1] = SkillJudgement(
        skill_id="K2", verdict="strong", evidence_id="E1", reason="Used"
    )
    junior = {**PROFILE, "experience": [{**PROFILE["experience"][0], "start": "2025-01"}]}
    await client.put("/api/v1/profile/me", json=junior)
    started = await client.post(BASE, json={"jd_text": JD})
    body = (await client.get(f"{BASE}/{started.json()['id']}")).json()

    assert body["raw_score"] == 90
    assert body["score"] == 60
    assert "3+ years" in body["seniority_note"]


async def test_same_job_and_profile_is_served_from_cache(
    client: AsyncClient, model: FakeModel
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    first = await client.post(BASE, json={"jd_text": JD})
    calls_after_first = model.calls
    second = await client.post(BASE, json={"jd_text": JD.upper()})

    assert second.json()["id"] == first.json()["id"]
    assert second.json()["status"] == "completed"
    assert model.calls == calls_after_first

    # Changing the profile makes the cached score stale.
    await client.put("/api/v1/profile/me", json={**PROFILE, "headline": "Senior engineer"})
    third = await client.post(BASE, json={"jd_text": JD})
    assert third.json()["id"] != first.json()["id"]


async def test_tracking_a_match_copies_its_score(client: AsyncClient, model: FakeModel) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    started = await client.post(BASE, json={"jd_text": JD})
    tracked = await client.post(
        "/api/v1/applications",
        json={
            "role": "Frontend Engineer",
            "company": "Acme Labs",
            "match_id": started.json()["id"],
        },
    )
    assert tracked.status_code == 201
    assert tracked.json()["match_score"] == 50


async def test_matches_are_private_to_their_owner(
    make_client: ClientFactory, model: FakeModel
) -> None:
    alice, bob = make_client(), make_client()
    await alice.put("/api/v1/profile/me", json=PROFILE)
    started = await alice.post(BASE, json={"jd_text": JD})
    match_id = started.json()["id"]

    assert (await bob.get(f"{BASE}/{match_id}")).status_code == 404
    assert (await bob.get(BASE)).json()["items"] == []
    stolen = await bob.post(
        "/api/v1/applications", json={"role": "x", "company": "y", "match_id": match_id}
    )
    assert stolen.status_code == 404
