"""Eval for the match score: every labelled profile against every labelled job
(see `match_cases.py`), run through the same code the API uses, with no
database and no network.

Run before and after changing how jobs are scored:

    uv run python -m backend.evals.matching            # the local engine
    uv run python -m backend.evals.matching --semantic # with the embedding model
    uv run python -m backend.evals.matching --model    # the model engine, for comparison
                                                       # (paid Gemini calls)

What it reports:
- false highs: a job from an unrelated field shown at HIGH or above. The worst
  mistake: it tells someone to apply for a job they cannot do.
- too generous: an unrelated job shown between LOW and HIGH.
- same-field hits: a job in the person's own field shown at HIGH or above.
- no score: the job could not be scored at all (the reason is printed).
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from backend.core.exceptions import AppError
from backend.evals.match_cases import JOBS, PROFILES, expected
from backend.modules.matches import service
from backend.modules.matches.local.semantic import get_matcher, warm_up
from backend.modules.matches.models import Job, Match
from backend.modules.profiles.schemas import ProfileRead

HIGH = 65
LOW = 40
# The reported job, and one that names tools everyone lists (Excel, SQL).
SAMPLE_JOBS = ("electrical_design_manager", "sales_executive")


@dataclass(frozen=True)
class Outcome:
    profile: str
    job: str
    expect: str
    score: int | None
    note: str


async def run_pair(profile_key: str, job_key: str, *, use_model: bool) -> Outcome:
    profile = ProfileRead.model_validate(PROFILES[profile_key])
    role, text = JOBS[job_key]
    expect = expected(profile_key, job_key)
    job = Job(role=role, jd_text=text, url=None, company=None, job_json=None)
    match = Match(job=job, profile_version=1)
    try:
        if use_model:
            await service.score_with_model(job, match, profile, user_api_key=None)
        else:
            service.score_without_model(job, match, profile, get_matcher())
    except AppError as exc:
        return Outcome(profile_key, job_key, expect, None, exc.detail)
    return Outcome(profile_key, job_key, expect, match.score, "model" if use_model else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic", action="store_true", help="load the embedding model")
    parser.add_argument("--all", action="store_true", help="print every pair, not just mistakes")
    parser.add_argument("--model", action="store_true", help="score with Gemini instead")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="only same-field pairs and every profile against two jobs (fewer model calls)",
    )
    args = parser.parse_args()
    if args.semantic:
        warm_up()

    async def run_all() -> list[Outcome]:
        pairs = [(p, j) for p in PROFILES for j in JOBS]
        if args.sample:
            pairs = [(p, j) for p, j in pairs if expected(p, j) == "high" or j in SAMPLE_JOBS]
        return [await run_pair(p, j, use_model=args.model) for p, j in pairs]

    outcomes = asyncio.run(run_all())
    low_cases = [o for o in outcomes if o.expect == "low"]
    high_cases = [o for o in outcomes if o.expect == "high"]
    false_high = [o for o in low_cases if o.score is not None and o.score >= HIGH]
    generous = [o for o in low_cases if o.score is not None and LOW < o.score < HIGH]
    hits = [o for o in high_cases if o.score is not None and o.score >= HIGH]
    unscored_high = [o for o in high_cases if o.score is None]
    missed = [o for o in high_cases if o.score is not None and o.score < HIGH]

    def line(o: Outcome) -> str:
        shown = "—" if o.score is None else str(o.score)
        return f"  {o.profile:<20} × {o.job:<28} expect {o.expect:<4} got {shown:>3}  {o.note}"

    if args.all:
        print("Every pair:")
        for o in outcomes:
            print(line(o))
        print()
    for title, items in (
        ("False highs (unrelated field scored high)", false_high),
        ("Too generous (unrelated field scored in the middle)", generous),
        ("Missed (own field scored below high)", missed),
        ("Own field not scored", unscored_high),
    ):
        if items:
            print(f"{title}:")
            for o in items:
                print(line(o))
            print()

    print(f"Pairs: {len(outcomes)}  (should be low: {len(low_cases)}, high: {len(high_cases)})")
    print(f"False highs:     {len(false_high)}/{len(low_cases)}")
    print(f"Too generous:    {len(generous)}/{len(low_cases)}")
    print(f"Same-field hits: {len(hits)}/{len(high_cases)}")
    print(f"Same-field not scored: {len(unscored_high)}/{len(high_cases)}")
    return 1 if false_high else 0


if __name__ == "__main__":
    sys.exit(main())
