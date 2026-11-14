"""Eval for reusing saved answers: every question in `question_cases.ASKED`
against the saved answer bank, through the same matcher the API uses. No
database, no network, no cost.

Run before and after changing how questions are matched:

    uv run python -m backend.evals.questions            # words alone (production default)
    uv run python -m backend.evals.questions --semantic # with the embedding model
    uv run python -m backend.evals.questions --semantic --sweep  # scores, to set thresholds

What it reports:
- wrong, filled: a wrong answer typed in as certain. The worst mistake: the user
  may not notice it before submitting. It should stay at 0.
- wrong, draft: a wrong answer offered as a draft to check. Costs a correction.
- right, filled / right, draft: the answer the user gave before, reused.
- missed: a saved answer fitted, but nothing was offered.
"""

import argparse
import sys
from collections import Counter

from backend.evals.question_cases import ASKED, SAVED
from backend.modules.matches.local.semantic import EmbeddingMatcher
from backend.modules.saved_answers.matching import Embed, match_questions


def _embedder() -> Embed:
    matcher = EmbeddingMatcher()
    matcher.load()
    return matcher.embed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--semantic", action="store_true", help="use the embedding model")
    parser.add_argument("--sweep", action="store_true", help="print every score")
    args = parser.parse_args()

    embed = _embedder() if args.semantic else None
    questions = [question for question, _ in ASKED]
    results = match_questions(questions, list(SAVED), embed)

    counts: Counter[str] = Counter()
    for (question, right_keys), result in zip(ASKED, results, strict=True):
        if result is None:
            outcome = "missed" if right_keys else "right, empty"
        elif result.key in right_keys:
            outcome = "right, filled" if result.confidence == "high" else "right, draft"
        else:
            outcome = "WRONG, filled" if result.confidence == "high" else "wrong, draft"
        counts[outcome] += 1
        if args.sweep or outcome in {"missed", "WRONG, filled", "wrong, draft"}:
            got = f"{result.key} ({result.confidence} {result.score})" if result else "nothing"
            print(f"  {outcome:<14} {question!r} -> {got}")

    total = len(ASKED)
    print(f"\n{total} questions, {'words + meaning' if embed else 'words alone'}:")
    for outcome in (
        "right, filled",
        "right, draft",
        "right, empty",
        "missed",
        "wrong, draft",
        "WRONG, filled",
    ):
        print(f"  {outcome:<14} {counts[outcome]:>3}")
    return 1 if counts["WRONG, filled"] else 0


if __name__ == "__main__":
    sys.exit(main())
