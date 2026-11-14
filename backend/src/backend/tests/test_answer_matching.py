"""The matcher that reuses saved answers, without a database or a model."""

import numpy as np
import pytest

from backend.evals.question_cases import ASKED, SAVED, key_for
from backend.modules.saved_answers.matching import (
    is_placeholder_key,
    match_questions,
    meaningful_words,
    names_something_else,
)


def test_synonyms_make_two_wordings_share_their_words() -> None:
    assert set(meaningful_words("What is your expected CTC?")) == set(
        meaningful_words("Salary expectations?")
    )
    assert "react" in meaningful_words("Have you used React.js?")


def test_questions_about_different_things_are_told_apart() -> None:
    react = set(meaningful_words("Have you worked on any project using React?"))
    angular = set(meaningful_words("Have you worked on any project using Angular?"))
    assert names_something_else(react, angular)
    laptop = set(meaningful_words("Do you have a laptop with stable internet?"))
    computer = set(meaningful_words("Do you have a laptop and reliable internet?"))
    assert not names_something_else(laptop, computer)


def test_a_rewording_is_filled_in_and_a_look_alike_is_not() -> None:
    react = key_for("Have you worked on any project using React?")
    results = match_questions(
        [
            "Do you have hands-on experience with React?",
            "Have you worked on any project using Angular?",
        ],
        [react, "notice_period"],
    )
    assert results[0] is not None and results[0].key == react
    assert results[0].confidence == "high"
    assert results[1] is None


def test_a_yes_no_question_is_never_answered_with_a_number() -> None:
    years = key_for("Total years of experience in Java")
    assert match_questions(["Have you worked with Java before?"], [years]) == [None]


def test_nothing_saved_or_nothing_meaningful_asked_matches_nothing() -> None:
    assert match_questions(["How soon can you join?"], []) == [None]
    assert match_questions(["Please enter"], ["notice_period"]) == [None]


def test_a_close_meaning_without_shared_words_is_only_a_draft() -> None:
    """The model's vectors are faked: "Why Infosys?" shares no word with "Why do
    you want to work here?", so even a close meaning is only offered to check."""

    def embed(texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0]] + [[0.7, 0.714]] * (len(texts) - 1))

    [result] = match_questions(["Why Infosys?"], ["why_this_role"], embed)
    assert result is not None and result.key == "why_this_role"
    assert result.confidence == "medium"
    assert result.question == "Why do you want to work here?"


def test_a_close_meaning_about_something_else_is_not_offered() -> None:
    """Close in meaning, but each names its own thing and nothing is shared."""
    strengths = key_for("What are your strengths?")

    def embed(texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0]] + [[0.75, 0.661]] * (len(texts) - 1))

    assert match_questions(["What are your weaknesses?"], [strengths], embed) == [None]


@pytest.mark.parametrize(("question", "right_keys"), [case for case in ASKED if not case[1]])
def test_eval_look_alikes_are_never_filled_in(question: str, right_keys: frozenset[str]) -> None:
    [result] = match_questions([question], list(SAVED))
    assert result is None or result.confidence == "medium"


@pytest.mark.parametrize(
    "key",
    [
        "q_this_field_is_required",
        "q_enter_text",
        "q_enter_numeric_value",
        "q_skip",
        "q_custom_question_radio_7520972",
        "q_7",
    ],
)
def test_placeholder_keys_are_never_matched(key: str) -> None:
    assert is_placeholder_key(key)
    assert match_questions(["Is this field required for the role?"], [key]) == [None]


@pytest.mark.parametrize(
    "key", ["notice_period", "q_how_did_you_hear_about_us", "q_are_you_willing_to_relocate"]
)
def test_real_question_keys_are_not_placeholders(key: str) -> None:
    assert not is_placeholder_key(key)
