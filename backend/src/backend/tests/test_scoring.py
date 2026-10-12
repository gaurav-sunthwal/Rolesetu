from datetime import date

from backend.modules.matches.scoring import (
    Judged,
    apply_seniority_cap,
    compute_score,
    years_of_experience,
)


def test_score_uses_spec_weights() -> None:
    results = [
        Judged(required=True, verdict="strong"),  # 2 of 2
        Judged(required=True, verdict="partial"),  # 1 of 2
        Judged(required=True, verdict="missing"),  # 0 of 2
        Judged(required=False, verdict="strong"),  # 1 of 1
        Judged(required=False, verdict="partial"),  # 0.5 of 1
    ]
    # 4.5 earned of 8 possible
    assert compute_score(results) == 56


def test_score_with_no_skills_is_zero() -> None:
    assert compute_score([]) == 0


def test_overlapping_jobs_are_counted_once() -> None:
    periods = [("2020-01", "2021-12"), ("2021-07", "2022-06")]
    assert years_of_experience(periods, date(2026, 1, 15)) == 2.5


def test_current_job_counts_up_to_today() -> None:
    assert years_of_experience([("2025-01", None)], date(2025, 12, 20)) == 1.0


def test_no_cap_when_experience_is_enough() -> None:
    assert apply_seniority_cap(90, min_years=3, candidate_years=4) == (90, None)
    assert apply_seniority_cap(90, min_years=None, candidate_years=0) == (90, None)


def test_score_is_capped_and_explained_when_short_on_years() -> None:
    score, note = apply_seniority_cap(90, min_years=3, candidate_years=2.5)
    assert score == 75
    assert note is not None and "capped at 75" in note

    score, note = apply_seniority_cap(90, min_years=5, candidate_years=1)
    assert score == 60
    assert note is not None and "scored 90" in note


def test_low_score_is_not_raised_by_the_cap() -> None:
    score, note = apply_seniority_cap(40, min_years=5, candidate_years=1)
    assert score == 40
    assert note is not None and "capped" not in note
