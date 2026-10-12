"""Turns the user's application history into things they can act on.

Rejection mails almost never say why. The useful signal is which jobs said no
and what those jobs asked for that the profile did not show, which the job
check recorded at the time. Nothing here reads mail text or calls a model.
"""

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class Outcome:
    """One application, with what its job check found (if it had one)."""

    status: str
    score: int | None = None
    experience_status: str | None = None
    required_years: float | None = None
    gaps: tuple[str, ...] = ()
    checked: bool = False


@dataclass(frozen=True)
class Finding:
    title: str
    detail: str


def _times(count: int) -> str:
    return "once" if count == 1 else f"{count} times"


def find_patterns(outcomes: list[Outcome]) -> list[Finding]:
    rejected = [item for item in outcomes if item.status == "rejected"]
    checked = [item for item in rejected if item.checked]
    progressed = [item for item in outcomes if item.status in ("interview", "offer")]
    findings: list[Finding] = []
    if not rejected:
        return findings

    short = [item for item in checked if item.experience_status in ("short", "well_short")]
    if short and len(short) * 2 >= len(checked):
        asked = sorted(item.required_years for item in short if item.required_years)
        typical = f" (typically {asked[len(asked) // 2]:g}+ years)" if asked else ""
        findings.append(
            Finding(
                title="Experience is the main reason",
                detail=(
                    f"{len(short)} of your {len(checked)} checked rejections asked for more "
                    f"experience than your profile shows{typical}. Aim at roles that ask for "
                    "what you have: the experience line on each job check tells you before "
                    "you apply."
                ),
            )
        )

    missing = Counter(gap for item in checked for gap in set(item.gaps))
    repeated = [(skill, count) for skill, count in missing.most_common(4) if count >= 2]
    if repeated:
        listed = ", ".join(f"{skill} ({_times(count)})" for skill, count in repeated)
        findings.append(
            Finding(
                title="Skills that keep coming up missing",
                detail=(
                    f"These were asked for by jobs that rejected you and are not on your "
                    f"profile: {listed}. If you have one, add it to your resume. If not, "
                    "it is the most useful thing to learn next."
                ),
            )
        )

    weak = [item for item in checked if item.score is not None and item.score < 50]
    if weak and len(weak) * 2 >= len(checked):
        findings.append(
            Finding(
                title="Many of these were long shots",
                detail=(
                    f"{len(weak)} of your {len(checked)} checked rejections scored under 50 "
                    "when you applied. Applications to jobs scoring 65 or more are a better "
                    "use of your time."
                ),
            )
        )

    strong_rejections = [item for item in checked if (item.score or 0) >= 70]
    if strong_rejections and not findings:
        findings.append(
            Finding(
                title="Your match was good, so look at the resume itself",
                detail=(
                    f"{len(strong_rejections)} rejections came from jobs where you scored 70 or "
                    "more. Use “Match your resume to this job” before applying, so your resume "
                    "uses the job's own title and wording."
                ),
            )
        )

    if progressed and checked:
        scores = [item.score for item in progressed if item.score is not None]
        if scores:
            findings.append(
                Finding(
                    title="What your interviews had in common",
                    detail=(
                        f"The {len(scores)} jobs that moved you forward scored "
                        f"{round(sum(scores) / len(scores))} on average. Use that as your bar."
                    ),
                )
            )

    unchecked = len(rejected) - len(checked)
    if unchecked:
        findings.append(
            Finding(
                title="Some rejections cannot be explained yet",
                detail=(
                    f"{unchecked} of your {len(rejected)} rejections have no job check, so we "
                    "do not know what those jobs asked for. Apply with the extension on and "
                    "each application keeps its job check."
                ),
            )
        )
    return findings
