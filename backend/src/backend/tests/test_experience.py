"""How much experience a job asks for, and what the candidate is told about it."""

import pytest

from backend.modules.matches.local.experience import read_experience
from backend.modules.matches.scoring import check_experience, score_cap


@pytest.mark.parametrize(
    ("text", "title", "expected"),
    [
        ("3+ years of experience with React and TypeScript.", None, (3, None, "stated")),
        ("Experience: 2 - 5 Yrs", None, (2, 5, "stated")),
        ("Experience\n2 - 5 years", None, (2, 5, "stated")),
        ("Minimum two years of professional experience.", None, (2, None, "stated")),
        ("You bring 5 yrs exp in mobile apps", None, (5, None, "stated")),
        # The largest minimum is the bar; a per-skill number does not lower it.
        (
            "5+ years of engineering experience. 2+ years with Kubernetes.",
            None,
            (5, None, "stated"),
        ),
        (
            "At least 6 months of hands-on experience with React Native.",
            None,
            (0.5, None, "stated"),
        ),
        ("24 months of experience required.", None, (2, None, "stated")),
        ("0-1 years of experience", None, (0, 1, "stated")),
        # A number about something else is not an experience requirement.
        (
            "We have built payments for 10 years. 4+ years of experience in Go.",
            None,
            (4, None, "stated"),
        ),
        ("3 years bond. Notice period 2 months.", "Software Engineer", (None, None, None)),
        ("Internship duration: 6 months. Stipend 15000.", "Software Engineer", (None, None, None)),
        # A stated requirement beats a preferred one; alone, a preference is kept as such.
        (
            "Experience required: 4 to 6 years\nNice to have: 8+ years of experience",
            None,
            (4, 6, "stated"),
        ),
        ("Ideally 3+ years of experience with AWS.", None, (3, None, "preferred")),
        ("Freshers can apply. Duration: 6 months", "React Intern", (0, None, "fresher")),
        ("Graduated in the last 2 years. Entry-level role.", None, (0, None, "fresher")),
        # No number anywhere: the title is the only clue.
        ("Build APIs with Python.", "Senior Backend Engineer", (5, None, "title")),
        ("Build APIs with Python.", "Staff Engineer", (7, None, "title")),
        ("Build APIs with Python.", "Software Engineering Intern", (0, None, "fresher")),
        ("Build APIs with Python.", "Software Engineer", (None, None, None)),
    ],
)
def test_reads_the_experience_a_posting_asks_for(
    text: str, title: str | None, expected: tuple[float | None, float | None, str | None]
) -> None:
    asked = read_experience(text, title)
    assert (asked.min_years, asked.max_years, asked.source) == expected


def test_every_job_gets_an_experience_verdict() -> None:
    score, met = check_experience(80, required_min=2, source="stated", candidate_years=3)
    assert (score, met.status) == (80, "meets")
    assert "2+ years" in met.summary and "you meet it" in met.summary

    score, unknown = check_experience(80, required_min=None, source=None, candidate_years=1.2)
    assert (score, unknown.status) == (80, "not_stated")
    assert "does not say" in unknown.summary and "about 1.2 years" in unknown.summary

    score, fresher = check_experience(80, required_min=0, source="fresher", candidate_years=0)
    assert (score, fresher.status) == (80, "open_to_freshers")
    assert "no dated work experience yet" in fresher.summary


def test_falling_short_is_said_plainly_and_caps_the_score() -> None:
    score, close = check_experience(90, required_min=3, source="stated", candidate_years=2.5)
    assert (score, close.status) == (75, "short")

    score, far = check_experience(
        90, required_min=5, source="stated", candidate_years=1.3, includes_internships=True
    )
    assert (score, far.status) == (60, "well_short")
    assert "5+ years" in far.summary and "internships included" in far.summary
    assert "big gap" in far.summary and "capped at 60" in far.summary

    # Already below the cap: said just as plainly, with nothing about a cap.
    score, low = check_experience(40, required_min=5, source="stated", candidate_years=1)
    assert (score, low.status) == (40, "well_short")
    assert "capped" not in low.summary


def test_a_guess_from_the_title_is_softer_than_a_stated_number() -> None:
    score, guessed = check_experience(
        90, required_min=5, source="title", quote="Senior", candidate_years=1
    )
    assert (score, guessed.status) == (75, "well_short")
    assert "“Senior”" in guessed.summary and "gives no number" in guessed.summary


def test_the_stated_cap_is_the_one_applied() -> None:
    """The app shows what more skills would do to a score using this cap, so it
    has to be the very limit the score itself was held to.
    """
    for source, years_short in [("stated", 4), ("stated", 0.5), ("title", 4), ("preferred", 4)]:
        score, verdict = check_experience(
            100, required_min=5, source=source, quote="Senior", candidate_years=5 - years_short
        )
        assert score == score_cap(verdict.status, source)
    assert score_cap("meets", "stated") is None
    assert score_cap("not_stated", None) is None
    assert score_cap("open_to_freshers", "fresher") is None
