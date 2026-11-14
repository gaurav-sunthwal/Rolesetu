"""Reuses a saved answer for a question asked in other words.

Job forms ask the same few dozen questions in endless wordings: "How soon can
you join?" is "What is your notice period?", "Do you own a laptop?" is "Do you
have a laptop with a stable internet connection?". Each saved answer is stored
under its question (its key: "notice_period", or "q_" and the question's words),
so finding the right answer means comparing questions with questions.

Two signals, both cheap:

- Words: the questions are cut down to the words that carry meaning, with
  common synonyms made the same ("ctc", "salary", "pay" all become "salary"),
  then overlapped. Free, instant, and always on.
- Meaning: when the embedding model is loaded, each question becomes a vector
  and the closest saved question is found by cosine similarity. It catches
  wordings that share no words ("Why should we select you?" and "Why are you the
  right candidate?").

A wrong answer typed into a form is worse than an empty box, so two guards keep
look-alikes apart. Questions that each name something the other does not
("...using React?" and "...using Angular?") are never filled in as certain. A
yes/no question is never answered with a number saved for a "how many" one.
What is not certain comes back as "medium": the extension fills it as a draft
and asks the user to check it.

The thresholds are measured, not guessed: `uv run python -m backend.evals.questions`.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

Confidence = Literal["high", "medium"]
# Turns texts into unit vectors, one row per text.
Embed = Callable[[list[str]], np.ndarray]

# Cosine similarity of two questions' vectors. In the eval, the closest saved
# question was the right one every time, but right answers scored from 0.47 and
# wrong look-alikes up to 0.67: a score alone cannot tell them apart, which is
# why the word checks below decide what is offered at all.
EMBED_HIGH = 0.80
EMBED_MEDIUM = 0.58
# Share of meaningful words two questions have in common.
WORDS_HIGH = 0.75
WORDS_MEDIUM = 0.50
# Two saved questions this close are a toss-up: neither is certain.
TOSS_UP = 0.03

# The questions the extension knows by kind are saved under the kind's name, not
# under their words, so their usual wordings are spelled out here.
KNOWN_PHRASINGS: dict[str, tuple[str, ...]] = {
    "why_this_role": (
        "Why are you interested in this role?",
        "Why do you want to work here?",
        "Why do you want to join this company?",
        "What interests you about this position?",
    ),
    "notice_period": (
        "What is your notice period?",
        "How soon can you join?",
        "When can you start?",
        "What is your earliest joining date?",
    ),
    "expected_ctc": (
        "What is your expected CTC?",
        "What are your salary expectations?",
        "What is your desired compensation?",
    ),
    "current_ctc": (
        "What is your current CTC?",
        "What is your current salary?",
    ),
    "relocation": (
        "Are you willing to relocate?",
        "Are you open to relocating to another city?",
    ),
    "work_authorization": (
        "Are you authorized to work in this country?",
        "Do you need visa sponsorship to work here?",
        "Do you have the right to work here?",
        "Are you legally eligible to work in India?",
    ),
    "date_of_birth": ("What is your date of birth?",),
    "gender": ("What is your gender?",),
    "nationality": ("What is your nationality?",),
    "postal_code": ("What is your postal code?", "What is your PIN code?"),
    "heard_from": (
        "How did you hear about this job?",
        "Where did you find this job posting?",
    ),
}


def _word_set(words: str) -> frozenset[str]:
    return frozenset(words.split())


_STOPWORDS = _word_set(
    "a an the to of in on for with at by from and or as is are was were be been being am "
    "do does did done you your yours yourselves we us our i me my it its this that these "
    "those there here any some have has had can could would will shall should may might "
    "please kindly if so what which who whom how when where why tell share give let "
    "about own currently ever before briefly brief want like know also just very "
    "use using used"
)

# Words that make a sentence a question about work without saying which one.
# They count for a little when two questions share them, and never make two
# questions different.
_GENERIC = _word_set(
    "experience build project role job position company team comfortable willing okay "
    "ok available able open fine good right valid total number per annum "
    "year month week day time full"
)

# Different words for one thing. Applied to whole words, before suffixes are cut.
_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(
        ["ctc", "salary", "compensation", "pay", "package", "remuneration", "stipend"], "salary"
    ),
    **dict.fromkeys(["expected", "expectation", "expectations", "desired"], "expect"),
    **dict.fromkeys(["join", "joining", "start", "starting", "begin", "commence"], "start"),
    **dict.fromkeys(["laptop", "computer", "pc", "desktop"], "laptop"),
    **dict.fromkeys(["internet", "wifi", "broadband", "connectivity"], "internet"),
    **dict.fromkeys(["relocate", "relocation", "relocating", "relocated"], "relocate"),
    **dict.fromkeys(["licence", "license", "licenses", "licences"], "license"),
    **dict.fromkeys(["bond", "agreement", "contract"], "bond"),
    **dict.fromkeys(["hire", "hiring", "select", "choose", "candidate", "fit"], "hire"),
    **dict.fromkeys(["yourself", "introduce", "introduction"], "intro"),
    **dict.fromkeys(["difficult", "challenging", "challenge", "hard", "tough"], "hard"),
    **dict.fromkeys(["office", "onsite"], "office"),
    **dict.fromkeys(
        ["authorized", "authorised", "allowed", "eligible", "permitted", "authorization"],
        "authorized",
    ),
    **dict.fromkeys(["remote", "wfh"], "remote"),
    **dict.fromkeys(
        ["worked", "working", "work", "experience", "experienced", "exposure", "hands"],
        "experience",
    ),
    **dict.fromkeys(["built", "build", "building", "created", "developed", "made"], "build"),
    **dict.fromkeys(["projects", "project"], "project"),
    **dict.fromkeys(["firm", "organisation", "organization", "company"], "company"),
    **dict.fromkeys(["position", "role", "job", "opening", "vacancy"], "role"),
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "twelve": "12",
}

_YES_NO_START = re.compile(
    r"^(?:do|does|did|have|has|are|is|was|were|can|could|will|would|should|shall)\b"
)
_NUMBER = re.compile(r"\bhow (?:many|much|long)\b|\byears? of\b|\btotal\b|\brate\b|\bnumber of\b")

QuestionShape = Literal["yes_no", "number", "open"]


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def meaningful_words(text: str) -> list[str]:
    """The words that carry a question's meaning, in a form two wordings share."""
    text = re.sub(r"\.js\b|\bjs\b", "", text.lower())
    text = text.replace("hands-on", "hands").replace("on-site", "onsite").replace("wi-fi", "wifi")
    words: list[str] = []
    for raw in re.findall(r"[a-z0-9+#]+", text):
        if raw in _STOPWORDS:
            continue
        word = _SYNONYMS.get(raw) or _SYNONYMS.get(_stem(raw)) or _stem(raw)
        if word not in _STOPWORDS:
            words.append(word)
    return words


def question_shape(text: str) -> QuestionShape:
    said = text.lower().strip()
    if _NUMBER.search(said):
        return "number"
    if _YES_NO_START.match(said):
        return "yes_no"
    return "open"


# Keys made from the words around a box rather than its question: an error message,
# a placeholder, a button. Older extension versions saved some ("q_this_field_is_
# required" = "7"), and any answer under one would be offered for every box.
_PLACEHOLDER_KEY = re.compile(
    r"^q_(?:this_(?:field|question)_is_required|(?:this_is_a_)?required(?:_field)?|optional|"
    r"enter(?:_\w+)?|type_here\w*|write_here\w*|your_answer|answer(?:_here)?|"
    r"skip|submit|next|back|continue|select\w*|choose\w*|placeholder|input|text|value|"
    r"custom_question_\w+|\d+|\w*\d{5,}\w*)$"
)


def is_placeholder_key(key: str) -> bool:
    """A key that names the box's surroundings, not a question a person would recognise."""
    return bool(_PLACEHOLDER_KEY.match(key))


def phrasings(key: str) -> tuple[str, ...]:
    """The wordings a saved answer's question is known by. None for a placeholder key."""
    if is_placeholder_key(key):
        return ()
    if key in KNOWN_PHRASINGS:
        return KNOWN_PHRASINGS[key]
    words = key.removeprefix("q_").replace("_", " ").strip()
    return (words,) if words else ()


def _weight(word: str) -> float:
    return 0.3 if word in _GENERIC else 1.0


def word_overlap(asked: set[str], saved: set[str]) -> float:
    """How much of two questions' meaning is shared, from 0 to 1.

    A short question fully covered by a longer one ("Do you own a laptop?" by
    "Do you have a laptop with stable internet?") counts almost as a full match.
    At least one specific word must be shared: two questions that only share
    "experience" are not the same question.
    """
    shared = asked & saved
    if not any(word not in _GENERIC for word in shared):
        return 0.0
    shared_weight = sum(_weight(word) for word in shared)
    both = shared_weight / sum(_weight(word) for word in asked | saved)
    covered = shared_weight / sum(_weight(word) for word in asked)
    return max(both, 0.85 * covered)


def names_something_else(asked: set[str], saved: set[str]) -> bool:
    """Each question names something specific the other does not, and they share
    nothing specific: "...using React?" and "...using Angular?". Questions that
    share their subject ("laptop and reliable internet", "laptop with stable
    internet") are only worded differently.
    """
    if (asked & saved) - _GENERIC:
        return False
    asked_only = {word for word in asked - saved if word not in _GENERIC}
    saved_only = {word for word in saved - asked if word not in _GENERIC}
    return bool(asked_only) and bool(saved_only)


@dataclass(frozen=True)
class QuestionMatch:
    key: str
    question: str
    confidence: Confidence
    score: float


@dataclass(frozen=True)
class _Candidate:
    key: str
    question: str
    score: float
    certain: bool


def _judge(
    asked_text: str,
    asked_words: set[str],
    key: str,
    texts: Sequence[str],
    similarities: Sequence[float] | None,
) -> _Candidate | None:
    """The best of one saved answer's wordings for one asked question."""
    best: _Candidate | None = None
    asked_shape = question_shape(asked_text)
    for index, text in enumerate(texts):
        words = set(meaningful_words(text))
        overlap = word_overlap(asked_words, words)
        similarity = similarities[index] if similarities is not None else 0.0
        score = max(overlap, similarity)
        reaches_high = overlap >= WORDS_HIGH or similarity >= EMBED_HIGH
        reaches_medium = overlap >= WORDS_MEDIUM or similarity >= EMBED_MEDIUM
        if not reaches_medium:
            continue

        shape = question_shape(text)
        if asked_shape != shape and "number" in (asked_shape, shape):
            continue
        different_thing = names_something_else(asked_words, words)
        if different_thing and not reaches_high:
            # A look-alike that is not even close in meaning: not offered at all.
            continue
        candidate = _Candidate(
            key=key, question=text, score=score, certain=reaches_high and not different_thing
        )
        if best is None or (candidate.certain, candidate.score) > (best.certain, best.score):
            best = candidate
    return best


def match_questions(
    asked: Sequence[str],
    saved_keys: Sequence[str],
    embed: Embed | None = None,
) -> list[QuestionMatch | None]:
    """The saved answer for each asked question, or None where nothing fits.

    `embed` is the embedding model; without it, matching is by words alone.
    """
    if not asked:
        return []
    texts_by_key = {key: phrasings(key) for key in dict.fromkeys(saved_keys)}
    texts_by_key = {key: texts for key, texts in texts_by_key.items() if texts}

    similarity_rows: list[dict[str, list[float]]] | None = None
    if embed is not None and texts_by_key:
        flat = [text for texts in texts_by_key.values() for text in texts]
        vectors = embed([*asked, *flat])
        asked_vectors, saved_vectors = vectors[: len(asked)], vectors[len(asked) :]
        all_similarities = asked_vectors @ saved_vectors.T
        similarity_rows = []
        for row in all_similarities:
            by_key: dict[str, list[float]] = {}
            offset = 0
            for key, texts in texts_by_key.items():
                by_key[key] = [float(value) for value in row[offset : offset + len(texts)]]
                offset += len(texts)
            similarity_rows.append(by_key)

    results: list[QuestionMatch | None] = []
    for index, asked_text in enumerate(asked):
        asked_words = set(meaningful_words(asked_text))
        if not asked_words:
            results.append(None)
            continue
        candidates = [
            candidate
            for key, texts in texts_by_key.items()
            if (
                candidate := _judge(
                    asked_text,
                    asked_words,
                    key,
                    texts,
                    similarity_rows[index][key] if similarity_rows is not None else None,
                )
            )
            is not None
        ]
        if not candidates:
            results.append(None)
            continue
        candidates.sort(key=lambda candidate: (candidate.certain, candidate.score), reverse=True)
        best = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        toss_up = (
            runner_up is not None
            and runner_up.certain == best.certain
            and best.score - runner_up.score < TOSS_UP
        )
        results.append(
            QuestionMatch(
                key=best.key,
                question=best.question,
                confidence="high" if best.certain and not toss_up else "medium",
                score=round(best.score, 3),
            )
        )
    return results
