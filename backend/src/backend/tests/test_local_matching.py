"""Scoring a job without a model: the skills dictionary, the job-description
reader, the judge, and the endpoint that uses them by default.
"""

from typing import Any

import pytest
from httpx import AsyncClient

from backend.ai import matching
from backend.modules.matches import scoring
from backend.modules.matches.local.catalog import find_skills
from backend.modules.matches.local.engine import score_locally
from backend.modules.matches.local.jd import parse_job
from backend.modules.matches.local.semantic import Support
from backend.modules.profiles.schemas import ProfileRead

FRONTEND_JD = """Frontend Engineer at Northwind (Bengaluru, hybrid)
We're looking for a frontend engineer with 2+ years of experience to build our dashboard.
Requirements: strong React and TypeScript, experience with REST APIs, solid CSS and responsive design, writing unit tests with Jest or Vitest, and Git. You should be comfortable with Docker for local development and PostgreSQL.
Nice to have: Next.js, GraphQL, experience with AWS, and familiarity with Figma.
You'll work closely with designers and backend engineers and ship features end to end.
Benefits
Free lunch and a Python book club. We go fast and express ideas."""  # noqa: E501

BACKEND_JD = """Senior Backend Engineer
About us
We are a fintech company. Our marketing site is built with React.
Responsibilities
- Design and build microservices in Python (FastAPI or Django)
- Own PostgreSQL schemas and Redis caching
Requirements
- 5+ years of backend experience
- Experience with a cloud provider such as AWS, GCP or Azure
- Docker and Kubernetes
Preferred qualifications
- Kafka, Terraform and Temporal.io
"""

PROFILE: dict[str, Any] = {
    "full_name": "Asha Rao",
    "headline": "Frontend developer",
    "location": None,
    "phone": None,
    "links": {},
    "skills": [
        {"id": "1", "name": "Figma", "level": "beginner"},
        {"id": "2", "name": "Git", "level": "advanced"},
        {"id": "3", "name": "MySQL"},
    ],
    "experience": [
        {
            "id": "e1",
            "title": "Frontend Developer",
            "company": "Phenko",
            "start": "2023-06",
            "end": None,
            "description": (
                "Built the seller dashboard in React and TypeScript with Next.js.\n"
                "Consumed REST APIs, wrote responsive layouts with Tailwind CSS.\n"
                "Added Vitest unit tests for the checkout flow."
            ),
        }
    ],
    "projects": [
        {
            "id": "p1",
            "name": "Realtime video app",
            "tech": ["WebRTC", "Node.js", "Socket.IO"],
            "description": "Peer to peer video rooms with a signalling server.",
        }
    ],
    "education": [],
    "version": 1,
    "completeness": 80,
    "updated_at": None,
}


def profile(**changes: Any) -> ProfileRead:
    return ProfileRead.model_validate({**PROFILE, **changes})


def names(text: str) -> list[str]:
    return [mention.skill.name for mention in find_skills(text)]


# --- the dictionary ----------------------------------------------------------


def test_aliases_resolve_to_one_name() -> None:
    assert names("ReactJS, React.js and React") == ["React", "React", "React"]
    assert names("Postgres, k8s, NodeJS, .NET Core") == [
        "PostgreSQL", "Kubernetes", "Node.js", "ASP.NET",
    ]  # fmt: skip


def test_a_skill_is_not_found_inside_another() -> None:
    assert names("JavaScript") == ["JavaScript"]  # not Java
    assert names("React Native") == ["React Native"]  # not React
    assert names("C++ and C#") == ["C++", "C#"]  # not C
    assert names("Tailwind CSS") == ["Tailwind CSS"]


def test_everyday_words_are_not_skills() -> None:
    assert names("We go fast, express ideas, and react quickly to spring sales.") == []
    assert names("Go, Express, React and Spring") == ["Go", "Express", "React", "Spring"]


# --- reading a job description -----------------------------------------------


def test_inline_requirements_and_nice_to_haves() -> None:
    job = parse_job(FRONTEND_JD)
    assert (job.role, job.company, job.min_years) == ("Frontend Engineer", "Northwind", 2)
    assert [item.name for item in job.requirements if item.required] == [
        "React", "TypeScript", "REST APIs", "CSS", "Responsive design", "Unit testing",
        "Jest or Vitest", "Git", "Docker", "PostgreSQL",
    ]  # fmt: skip
    assert [item.name for item in job.requirements if not item.required] == [
        "Next.js", "GraphQL", "AWS", "Figma",
    ]  # fmt: skip
    # The benefits section mentions Python, which is not a requirement.
    assert "Python" not in [item.name for item in job.requirements]


def test_sections_alternatives_and_unknown_tools() -> None:
    job = parse_job(BACKEND_JD)
    assert (job.role, job.min_years) == ("Senior Backend Engineer", 5)
    assert [item.name for item in job.requirements if item.required] == [
        "Microservices", "Python", "FastAPI or Django", "PostgreSQL", "Redis",
        "AWS or GCP or Azure", "Docker", "Kubernetes",
    ]  # fmt: skip
    # "Temporal.io" is not in the dictionary but is recognised as a tool name.
    assert [item.name for item in job.requirements if not item.required] == [
        "Kafka", "Terraform", "Temporal.io",
    ]  # fmt: skip
    assert "React" not in [item.name for item in job.requirements]  # only in "About us"


def test_a_skill_named_twice_keeps_the_stronger_requirement() -> None:
    job = parse_job("Docker is a plus.\nRequirements\nYou must know Docker and Git.")
    assert [(item.name, item.required) for item in job.requirements] == [
        ("Docker", True),
        ("Git", True),
    ]


# --- judging against a profile -----------------------------------------------


def verdicts(result: Any) -> dict[str, str]:
    return {item.name: item.verdict for item in result.judgements}


def test_each_kind_of_verdict_and_its_reason() -> None:
    result = score_locally(profile(), FRONTEND_JD)
    found = {item.name: item for item in result.judgements}

    assert found["React"].verdict == "strong"
    assert found["React"].evidence_label == "Frontend Developer at Phenko"
    assert found["React"].evidence_text == (
        "Built the seller dashboard in React and TypeScript with Next.js."
    )
    # Using Tailwind CSS is using CSS.
    assert found["CSS"].verdict == "strong" and "Tailwind CSS" in found["CSS"].reason
    # Named in the skills list: counts in full.
    assert found["Git"].verdict == "strong" and "Listed" in found["Git"].reason
    # A close substitute, said plainly.
    assert found["PostgreSQL"].verdict == "partial" and "MySQL" in found["PostgreSQL"].reason
    # Either option satisfies an "or".
    assert found["Jest or Vitest"].verdict == "strong"
    assert found["Docker"].verdict == "missing" and found["Docker"].evidence_text is None
    # REST experience is not GraphQL experience.
    assert found["GraphQL"].verdict == "missing"

    score = scoring.compute_score(
        [scoring.Judged(item.required, item.verdict) for item in result.judgements]
    )
    # required: 8 strong, 1 partial, 1 missing = 17 of 20; nice: 2 strong = 2 of 4
    assert score == 79


def test_same_input_always_gives_the_same_result() -> None:
    first = score_locally(profile(), FRONTEND_JD)
    second = score_locally(profile(), FRONTEND_JD)
    assert first.judgements == second.judgements


def test_a_skill_only_the_candidate_names_is_still_recognised() -> None:
    skills = [*PROFILE["skills"], {"id": "9", "name": "Zeebe"}]
    result = score_locally(profile(skills=skills), "Requirements: Python and Zeebe workflows.")
    assert verdicts(result) == {"Python": "missing", "Zeebe": "strong"}


def test_text_with_no_recognisable_skills_gives_nothing() -> None:
    assert score_locally(profile(), "We are a friendly team that loves coffee.").judgements == []


class FakeMatcher:
    """Stands in for the embedding model: says which line supports which skill."""

    def __init__(self, supported: dict[str, str]) -> None:
        self.supported = supported
        self.asked: list[str] = []

    def best_support(self, skill: str, lines: list[str]) -> Support | None:
        self.asked.append(skill)
        wanted = self.supported.get(skill)
        for index, line in enumerate(lines):
            if wanted and wanted in line:
                return Support(index, 0.9)
        return None


def test_a_skill_shown_but_not_named_earns_partial_and_quotes_the_line() -> None:
    matcher = FakeMatcher({"Docker": "signalling server"})
    result = score_locally(profile(), FRONTEND_JD, matcher)
    found = {item.name: item for item in result.judgements}

    assert found["Docker"].verdict == "partial"
    assert found["Docker"].evidence_label == "Project: Realtime video app"
    assert found["Docker"].evidence_text == "Peer to peer video rooms with a signalling server."
    assert "suggests related experience" in found["Docker"].reason
    assert found["AWS"].verdict == "missing"  # the model found nothing for it


def test_the_model_is_only_asked_about_skills_the_dictionary_missed() -> None:
    matcher = FakeMatcher({})
    score_locally(profile(), FRONTEND_JD, matcher)
    # React, Git, PostgreSQL and the rest were settled by lookup.
    assert sorted(matcher.asked) == ["AWS", "Docker", "GraphQL"]


# --- the endpoint ------------------------------------------------------------

BASE = "/api/v1/matches"
SAVED_PROFILE = {
    key: PROFILE[key]
    for key in ("full_name", "headline", "skills", "experience", "projects", "education")
}


@pytest.fixture
def no_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the local engine must not call a model")

    monkeypatch.setattr(matching, "generate_structured", forbidden)


@pytest.mark.usefixtures("no_model_calls")
async def test_a_check_completes_in_the_request_without_a_model(client: AsyncClient) -> None:
    await client.put("/api/v1/profile/me", json=SAVED_PROFILE)
    response = await client.post(BASE, json={"jd_text": FRONTEND_JD})
    body = response.json()

    assert response.status_code == 202
    assert body["status"] == "completed"  # nothing to poll for
    assert body["score"] == 79
    assert (body["role"], body["company"]) == ("Frontend Engineer", "Northwind")
    assert body["gaps"] == ["Docker", "GraphQL", "AWS"]
    assert body["seniority_note"] is None  # about 3 years against a 2+ requirement

    again = await client.post(BASE, json={"jd_text": FRONTEND_JD})
    assert again.json()["id"] == body["id"]  # served from cache


@pytest.mark.usefixtures("no_model_calls")
async def test_seniority_cap_still_applies(client: AsyncClient) -> None:
    await client.put("/api/v1/profile/me", json=SAVED_PROFILE)
    senior = FRONTEND_JD.replace("2+ years", "8+ years")
    body = (await client.post(BASE, json={"jd_text": senior})).json()
    assert body["raw_score"] == 79 and body["score"] == 60
    assert "8+ years" in body["seniority_note"]


@pytest.mark.usefixtures("no_model_calls")
async def test_text_without_skills_is_rejected(client: AsyncClient) -> None:
    await client.put("/api/v1/profile/me", json=SAVED_PROFILE)
    prose = "We are a friendly team that loves coffee and long walks on the beach. " * 4
    response = await client.post(BASE, json={"jd_text": prose})
    assert response.status_code == 422
    assert "could not find any skills" in response.json()["detail"]
    assert (await client.get(BASE)).json()["items"] == []


# --- working out a title when the text does not lead with one ------------------

BODY_ONLY = (
    "About the job\nKey Responsibilities:\n"
    "1. Build web interfaces using HTML, CSS, JavaScript, and React.\n"
    "2. Develop backend services using Python, Node.js or Flask.\n"
)


def test_title_from_a_labelled_line() -> None:
    job = parse_job("Description\nBuild UIs in React Native.\nRole: Full Stack Developer\n")
    assert job.role == "Full Stack Developer"


def test_title_from_a_phrase_in_the_text() -> None:
    job = parse_job(
        "About the internship\nAs a react native engineer (iOS) intern at Humanity Founders, "
        "you will work on mobile apps using React Native.\n"
    )
    assert (job.role, job.company) == ("React native engineer (iOS) intern", "Humanity Founders")


def test_title_from_the_listing_link() -> None:
    url = (
        "https://internshala.com/job/detail/"
        "fresher-remote-full-stack-ai-developer-job-at-megaminds-it-services1791546472"
    )
    job = parse_job(BODY_ONLY, (), url)
    assert (job.role, job.company) == ("Full Stack AI Developer", "Megaminds IT Services")


def test_a_search_page_link_is_not_mistaken_for_a_listing() -> None:
    url = "https://internshala.com/jobs/android-app-development,front-end-development-jobs/x"
    assert parse_job(BODY_ONLY, (), url).role == "Full Stack Developer"  # inferred instead


def test_title_inferred_from_the_skills_when_nothing_names_it() -> None:
    assert parse_job(BODY_ONLY).role == "Full Stack Developer"
    android = "Role Overview:\nDevelop Android apps using Kotlin and Jetpack Compose.\n"
    assert parse_job(android + "This is an internship.").role == "Android Developer Intern"
    # One mention of dashboards does not make it a data role.
    web = "Requirements:\nReact and TypeScript. You will build dashboards.\n"
    assert parse_job(web).role == "Frontend Developer"


def test_a_section_heading_is_not_a_title() -> None:
    job = parse_job("Selected intern's day-to-day responsibilities include:\n1. Write Python.\n")
    assert job.role == "Backend Developer Intern"
