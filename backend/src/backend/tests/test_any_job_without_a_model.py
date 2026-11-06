"""Every job is scored without a model: postings outside software, generic
career-site postings, and skills the dictionary has never heard of.
"""

from typing import Any

from backend.evals.match_cases import PROFILES
from backend.modules.matches import service
from backend.modules.matches.local.catalog import find_skills
from backend.modules.matches.local.jd import parse_job
from backend.modules.matches.local.phrases import find_phrases
from backend.modules.matches.models import Job, Match
from backend.modules.profiles.schemas import ProfileRead
from backend.modules.tailoring.keywords import clean_title, suggest_headline

# A real posting from an Oracle careers page: it names few tools, and asks for
# "software development" and "code reviews" in plain words.
INTERN_POSTING = """Intern Bachelors Software Eng
As an Intern Bachelors Software Eng here at Honeywell, you will gain hands-on experience in software development, working on real-world projects.
Key Responsibilities
Learn and apply software engineering principles
Participate in code reviews and contribute to software development
Collaborate with crossfunctional teams to design and develop software solutions
Gain exposure to different programming languages, tools, and technologies
YOU MUST HAVE
Enrollment in a Bachelor's program in Software Engineering or related field
Basic understanding of software development principles
WE VALUE
Pursuing an advanced degree in Software Engineering or related field
Experience with programming languages such as Java, Python, or C++
Strong problem-solving skills and a passion for technology
About Us
Honeywell is a global automation company serving the building and process sectors.
"""  # noqa: E501

FULL_STACK_INTERN: dict[str, Any] = {
    "full_name": "Test Person",
    "headline": "Full Stack & AI Engineer",
    "location": None,
    "phone": None,
    "links": {},
    "skills": [{"id": f"s{i}", "name": n} for i, n in enumerate(["Python", "Java", "Code review"])],
    "experience": [
        {
            "id": "e1",
            "title": "Full Stack Developer Intern",
            "company": "Terminal 2",
            "start": "2025-09",
            "end": None,
            "description": "Build and maintain a production commerce app with React Native.",
        }
    ],
    "projects": [
        {
            "id": "p1",
            "name": "Rolesetu",
            "tech": ["Python", "FastAPI"],
            "description": "Scores jobs against resumes.",
        }
    ],
    "education": [{"id": "d1", "school": "MIT-WPU", "degree": "B.Tech", "field": "Computer"}],
    "version": 1,
    "completeness": 90,
    "updated_at": None,
}


def score(profile: dict[str, Any], role: str, text: str) -> Match:
    job = Job(role=role, jd_text=text, url=None, company=None, job_json=None)
    match = Match(job=job, profile_version=1)
    service.score_without_model(job, match, ProfileRead.model_validate(profile), None)
    return match


def test_a_generic_software_posting_is_a_good_fit_for_a_developer() -> None:
    """The reported case: held at 60 with one skill checked, after a 30 second model call."""
    match = score(FULL_STACK_INTERN, "Intern Bachelors Software Eng", INTERN_POSTING)
    verdicts = {item["name"]: (item["required"], item["verdict"]) for item in match.skill_results}
    assert verdicts["Software development"] == (True, "strong")
    assert verdicts["Code review"][0] is True
    assert verdicts["Java or Python or C++"] == (False, "strong")
    caps = match.experience["assessment"]["caps"] if match.experience else []
    assert caps == []
    assert match.score is not None and match.score >= 70
    assert match.experience is not None
    assert match.experience["assessment"]["field_fit"]["status"] == "same"


def test_a_role_in_a_field_shows_that_fields_core_work() -> None:
    match = score(FULL_STACK_INTERN, "Software Engineer", "Requirements\n- Software development")
    item = match.skill_results[0]
    assert item["verdict"] == "strong"
    assert "Full Stack Developer Intern" in (item["evidence_label"] or "")


def test_soft_skills_and_category_words_are_not_requirements() -> None:
    names = [item.name for item in parse_job(INTERN_POSTING).requirements]
    assert not any("problem" in name.lower() or "passion" in name.lower() for name in names)
    assert not any(name.lower() in {"programming languages", "technologies"} for name in names)


def test_skills_the_dictionary_does_not_know_are_read_from_the_wording() -> None:
    sentence = "Working knowledge of building automation systems and fire alarm panels."
    names = [skill.name for skill in find_phrases(sentence, find_skills(sentence))]
    assert names == ["Building automation systems", "Fire alarm panels"]


def test_a_phrase_is_proven_by_work_that_names_it() -> None:
    profile = {
        **PROFILES["electrical_engineer"],
        "experience": [
            {
                **PROFILES["electrical_engineer"]["experience"][0],
                "description": "Commissioned building automation systems for hospitals.",
            }
        ],
    }
    text = "Requirements\n- Experience with building automation systems."
    found = {
        item["name"]: item["verdict"] for item in score(profile, "Engineer", text).skill_results
    }
    assert found["Building automation systems"] == "strong"


def test_a_job_in_another_field_is_turned_away_without_a_skill_read() -> None:
    match = score(FULL_STACK_INTERN, "ICU Staff Nurse", "Requirements\n- BLS and ACLS.\n- Epic.")
    assert match.skill_results == []
    assert match.score == 35
    assert "not your role" in (match.experience or {})["assessment"]["field_fit"]["summary"]


def test_a_short_title_from_a_careers_site_is_read_in_full() -> None:
    assert clean_title("Intern Bachelors Software Eng") == "Intern Software Engineer"
    assert suggest_headline("FULL STACK DEVELOPER", "Intern Bachelors Software Eng") == (
        "SOFTWARE ENGINEER"
    )
