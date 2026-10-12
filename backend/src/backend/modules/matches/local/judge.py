"""Decides how well the profile supports each skill a job asks for.

    strong    a role or project uses the skill, or the person lists it
    partial   the profile shows a close substitute, or a line of work that
              means the skill without naming it (found by the embedding model)
    missing   nothing on the profile supports it

Every verdict carries the piece of the profile it came from, so the result can
always be explained and nothing is inferred that the profile does not say.
"""

import re
from dataclasses import dataclass
from typing import Literal

from backend.modules.matches.local.catalog import Skill, find_skills, implied_by
from backend.modules.matches.local.jd import Requirement
from backend.modules.matches.local.semantic import Matcher, usable_lines
from backend.modules.profiles.schemas import ProfileRead

Verdict = Literal["strong", "partial", "missing"]
_SNIPPET_LIMIT = 280
_RANK = {"strong": 3, "listed": 2, "related": 1, "missing": 0}


@dataclass(frozen=True)
class Evidence:
    # "work" is something the person did; "listed" is something they only named.
    kind: Literal["work", "listed"]
    label: str
    text: str
    reason: str


@dataclass(frozen=True)
class Judgement:
    name: str
    required: bool
    verdict: Verdict
    evidence_label: str | None
    evidence_text: str | None
    reason: str


def extra_names(profile: ProfileRead) -> tuple[str, ...]:
    """The candidate's own skill and tech names, so ones the dictionary does not
    know are still recognised in a job description.
    """
    names = [skill.name for skill in profile.skills]
    names += [tech for project in profile.projects for tech in project.tech]
    return tuple(sorted({name.strip() for name in names if name.strip()}, key=str.lower))


def build_evidence(profile: ProfileRead) -> list[Evidence]:
    items: list[Evidence] = []
    for job in profile.experience:
        label = f"{job.title} at {job.company}"
        items.append(
            Evidence("work", label, job.description, f"Shown in your role as {label.rstrip('.')}.")
        )
    for project in profile.projects:
        text = "\n".join(part for part in (", ".join(project.tech), project.description) if part)
        items.append(
            Evidence(
                "work", f"Project: {project.name}", text, f"Shown in your project {project.name}."
            )
        )
    for skill in profile.skills:
        level = f" ({skill.level})" if skill.level else ""
        items.append(
            Evidence(
                "listed",
                "Listed skill",
                f"{skill.name}{level}",
                "Listed in your skills.",
            )
        )
    return [item for item in items if item.text.strip()]


def _snippet(text: str, start: int, end: int) -> str:
    """The line or bullet around a mention, trimmed for display."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line = text[line_start : line_end if line_end != -1 else len(text)].strip()
    if len(line) <= _SNIPPET_LIMIT:
        return line
    offset = start - line_start
    begin = max(0, min(offset - _SNIPPET_LIMIT // 3, len(line) - _SNIPPET_LIMIT))
    cut = line[begin : begin + _SNIPPET_LIMIT].strip()
    return f"{'…' if begin else ''}{cut}{'…' if begin + _SNIPPET_LIMIT < len(line) else ''}"


class ProfileIndex:
    """Which skills each part of the profile shows, computed once per check."""

    def __init__(self, profile: ProfileRead, matcher: Matcher | None = None) -> None:
        self.extra = extra_names(profile)
        self.matcher = matcher
        # Every line of real work, for the by-meaning pass.
        self.work_lines: list[tuple[Evidence, str]] = []
        # skill -> best (evidence, snippet) of each kind
        self.work: dict[Skill, tuple[Evidence, str]] = {}
        self.listed: dict[Skill, tuple[Evidence, str]] = {}
        for item in build_evidence(profile):
            target = self.work if item.kind == "work" else self.listed
            if item.kind == "work":
                self.work_lines.extend((item, line) for line in usable_lines(item.text))
            for mention in find_skills(item.text, self.extra):
                snippet = _snippet(item.text, mention.start, mention.end)
                target.setdefault(mention.skill, (item, snippet))
                # Using a tool demonstrates what it is built on (Tailwind CSS -> CSS).
                for implied in implied_by(mention.skill):
                    via = Evidence(
                        item.kind,
                        item.label,
                        item.text,
                        f"Shown through {mention.skill.name}. {item.reason}",
                    )
                    target.setdefault(implied, (via, snippet))

    def _related(self, skill: Skill) -> tuple[Skill, Evidence, str] | None:
        if skill.group is None:
            return None
        for source in (self.work, self.listed):
            for other, (item, snippet) in source.items():
                if other.group == skill.group and other != skill:
                    return other, item, snippet
        return None

    def _by_meaning(
        self, requirement: Requirement
    ) -> tuple[Verdict, Evidence | None, str | None, str] | None:
        """Last resort for a skill nothing on the profile names: is there a line
        of work that means it? Worth partial credit, and the line is shown.
        """
        if self.matcher is None or not self.work_lines:
            return None
        lines = [line for _, line in self.work_lines]
        found = [
            support
            for skill in requirement.options
            if (support := self.matcher.best_support(skill.name, lines)) is not None
        ]
        if not found:
            return None
        support = max(found, key=lambda item: item.similarity)
        item, line = self.work_lines[support.line_index]
        reason = "Not named on your profile, but this line suggests related experience."
        return "partial", item, line, reason

    def judge(self, requirement: Requirement) -> Judgement:
        best_rank = 0
        best: tuple[Verdict, Evidence | None, str | None, str] = (
            "missing",
            None,
            None,
            "Nothing on your profile mentions this.",
        )
        for skill in requirement.options:
            if skill in self.work:
                item, snippet = self.work[skill]
                rank, candidate = _RANK["strong"], ("strong", item, snippet, item.reason)
            elif skill in self.listed:
                item, snippet = self.listed[skill]
                # A skill the person lists counts in full: nobody writes "used Git"
                # in a bullet. A role or project is still preferred as the evidence.
                rank, candidate = _RANK["listed"], ("strong", item, snippet, item.reason)
            elif (related := self._related(skill)) is not None:
                other, item, snippet = related
                reason = f"Not on your profile, but you have {other.name}, a closely related skill."
                rank, candidate = _RANK["related"], ("partial", item, snippet, reason)
            else:
                continue
            if rank > best_rank:
                best_rank, best = rank, candidate  # type: ignore[assignment]

        if best_rank == 0:
            best = self._by_meaning(requirement) or best
        verdict, cited, quote, reason = best
        return Judgement(
            name=requirement.name,
            required=requirement.required,
            verdict=verdict,
            evidence_label=cited.label if cited else None,
            evidence_text=re.sub(r"\s+", " ", quote).strip() if quote else None,
            reason=reason,
        )
