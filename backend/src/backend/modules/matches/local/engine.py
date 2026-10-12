"""Scores a job against a profile locally: parse the job, judge each skill.

Pass a `matcher` to add the by-meaning pass; without one, only the dictionary is used.
"""

from dataclasses import dataclass

from backend.modules.matches.local.jd import ParsedJob, parse_job
from backend.modules.matches.local.judge import Judgement, ProfileIndex
from backend.modules.matches.local.semantic import Matcher
from backend.modules.profiles.schemas import ProfileRead

# Bump when the dictionary or the rules change, so stored results record
# which version produced them.
ENGINE_VERSION = "local.v4"


@dataclass(frozen=True)
class LocalMatch:
    job: ParsedJob
    judgements: list[Judgement]


def score_locally(
    profile: ProfileRead,
    jd_text: str,
    matcher: Matcher | None = None,
    url: str | None = None,
) -> LocalMatch:
    index = ProfileIndex(profile, matcher)
    job = parse_job(jd_text, index.extra, url)
    return LocalMatch(job=job, judgements=[index.judge(item) for item in job.requirements])
