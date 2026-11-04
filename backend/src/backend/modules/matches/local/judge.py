"""Decides how well the profile supports each skill a job asks for.

    strong    a recent role, or a project, shows the person using the skill
    partial   the skill is only listed, was last used in a role that ended
              long ago, has a close substitute on the profile, or a line of
              work means it without naming it (found by the embedding model)
    missing   nothing on the profile supports it

Listing a skill is a claim; using it in a job is proof. Only proof earns full
credit, which is what an interviewer checks for too.

Every verdict carries the piece of the profile it came from, so the result can
always be explained and nothing is inferred that the profile does not say.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from backend.modules.matches.local import fields
from backend.modules.matches.local.catalog import Skill, find_skills, implied_by, shown_by_field
from backend.modules.matches.local.jd import Requirement
from backend.modules.matches.local.semantic import Matcher, usable_lines
from backend.modules.profiles.schemas import ProfileRead

Verdict = Literal["strong", "partial", "missing"]
_SNIPPET_LIMIT = 280
_RANK = {"strong": 4, "dated": 3, "listed": 2, "related": 1, "missing": 0}
# A skill last used in a role that ended longer ago than this is out of date.
STALE_AFTER_YEARS = 6
# Share of a phrase's words a line of work must contain to count as related work.
PHRASE_PARTIAL_SHARE = 0.5
# Words that carry no meaning of their own in a skill phrase.
_STOPWORDS = frozenset(
    {"a", "an", "the", "and", "or", "of", "in", "on", "for", "with", "to", "by", "at", "as",
     "from", "into", "using", "use", "via", "etc", "its", "our", "your"}
)  # fmt: skip
_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ers", "er", "ed", "es", "s")


def _stem(word: str) -> str:
    """A crude stem, so "designed", "designs" and "designing" are one word."""
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def content_words(text: str) -> frozenset[str]:
    tokens = re.findall(r"[a-z][a-z0-9+#]*", text.lower())
    return frozenset(_stem(token) for token in tokens if token not in _STOPWORDS)


@dataclass(frozen=True)
class Evidence:
    # "work" is something the person did; "listed" is something they only named.
    kind: Literal["work", "listed"]
    label: str
    text: str
    reason: str
    # 'YYYY-MM' the role ended; None for a current role, a project or a listed skill.
    ended: str | None = None


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
            Evidence(
                "work",
                label,
                job.description,
                f"Shown in your role as {label.rstrip('.')}.",
                job.end,
            )
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

    def __init__(
        self, profile: ProfileRead, matcher: Matcher | None = None, today: date | None = None
    ) -> None:
        self.extra = extra_names(profile)
        self.matcher = matcher
        self.today = today or date.today()
        # Every line of real work, for the by-meaning pass.
        self.work_lines: list[tuple[Evidence, str]] = []
        # Every line of the profile with its words, for judging phrases.
        self.worded_lines: list[tuple[Evidence, str, frozenset[str]]] = []
        # skill -> best (evidence, snippet) of each kind
        self.work: dict[Skill, tuple[Evidence, str]] = {}
        self.listed: dict[Skill, tuple[Evidence, str]] = {}
        for item in build_evidence(profile):
            target = self.work if item.kind == "work" else self.listed
            if item.kind == "work":
                self.work_lines.extend((item, line) for line in usable_lines(item.text))
            self.worded_lines.extend(
                (item, line.strip(), content_words(line))
                for line in item.text.splitlines()
                if line.strip()
            )
            for mention in find_skills(item.text, self.extra):
                snippet = _snippet(item.text, mention.start, mention.end)
                self._keep(target, mention.skill, item, snippet)
                # Using a tool demonstrates what it is built on (Tailwind CSS -> CSS).
                for implied in implied_by(mention.skill):
                    via = Evidence(
                        item.kind,
                        item.label,
                        item.text,
                        f"Shown through {mention.skill.name}. {item.reason}",
                        item.ended,
                    )
                    self._keep(target, implied, via, snippet)

        # A role in a line of work shows that work's core skills, named or not:
        # a Full Stack Developer has done software development.
        for role in profile.experience:
            field = fields.field_of(role.title)
            if field is None:
                continue
            label = f"{role.title} at {role.company}"
            via = Evidence(
                "work",
                label,
                role.title,
                f"Your role as {label.rstrip('.')} is {field.label} work.",
                role.end,
            )
            for skill in shown_by_field(field.key):
                self._keep(self.work, skill, via, role.title)
            self.worded_lines.append((via, role.title, content_words(role.title)))

    def _years_ago(self, item: Evidence) -> float:
        if item.ended is None:
            return 0.0
        year, month = (int(part) for part in item.ended.split("-"))
        return (self.today.year - year) + (self.today.month - month) / 12

    def _keep(
        self,
        target: dict[Skill, tuple[Evidence, str]],
        skill: Skill,
        item: Evidence,
        snippet: str,
    ) -> None:
        """Keeps the most recent place a skill was used: that is the one that counts."""
        current = target.get(skill)
        if current is None or self._years_ago(item) < self._years_ago(current[0]):
            target[skill] = (item, snippet)

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

    def _by_words(
        self, requirement: Requirement
    ) -> tuple[int, tuple[Verdict, Evidence | None, str | None, str]] | None:
        """For a phrase the dictionary does not know: the profile line that
        shares the most of its words. All of them in recent work is proof; all
        of them only in the skills list, or most of them in work, is partial.
        """
        best: tuple[int, tuple[Verdict, Evidence | None, str | None, str]] | None = None
        for skill in requirement.options:
            wanted = content_words(skill.name)
            if not wanted:
                continue
            for item, line, words in self.worded_lines:
                share = len(wanted & words) / len(wanted)
                if share == 1 and item.kind == "work":
                    if self._years_ago(item) <= STALE_AFTER_YEARS:
                        found = (_RANK["strong"], ("strong", item, line, item.reason))
                    else:
                        reason = (
                            f"Last shown in {item.label}, which ended in {(item.ended or '')[:4]}. "
                            "Employers look for recent use."
                        )
                        found = (_RANK["dated"], ("partial", item, line, reason))
                elif share == 1:
                    reason = (
                        "Listed in your skills, but no role or project shows you using it. "
                        "Add a line about where you used it."
                    )
                    found = (_RANK["listed"], ("partial", item, line, reason))
                elif share >= PHRASE_PARTIAL_SHARE and len(wanted) >= 2 and item.kind == "work":
                    reason = "Not named as such on your profile, but this line covers part of it."
                    found = (_RANK["related"], ("partial", item, line, reason))
                else:
                    continue
                if best is None or found[0] > best[0]:
                    best = found  # type: ignore[assignment]
        return best

    def judge(self, requirement: Requirement) -> Judgement:
        best_rank = 0
        best: tuple[Verdict, Evidence | None, str | None, str] = (
            "missing",
            None,
            None,
            "Nothing on your profile mentions this.",
        )
        for skill in requirement.options:
            if skill in self.work and self._years_ago(self.work[skill][0]) <= STALE_AFTER_YEARS:
                item, snippet = self.work[skill]
                rank, candidate = _RANK["strong"], ("strong", item, snippet, item.reason)
            elif skill in self.work:
                item, snippet = self.work[skill]
                reason = (
                    f"Last used in your role as {item.label}, which ended in "
                    f"{(item.ended or '')[:4]}. Employers look for recent use."
                )
                rank, candidate = _RANK["dated"], ("partial", item, snippet, reason)
            elif skill in self.listed:
                item, snippet = self.listed[skill]
                # Listed but never shown in a role or project: a claim, not proof.
                reason = (
                    "Listed in your skills, but no role or project shows you using it. "
                    "Add a line about where you used it."
                )
                rank, candidate = _RANK["listed"], ("partial", item, snippet, reason)
            elif (related := self._related(skill)) is not None:
                other, item, snippet = related
                reason = f"Not on your profile, but you have {other.name}, a closely related skill."
                rank, candidate = _RANK["related"], ("partial", item, snippet, reason)
            else:
                continue
            if rank > best_rank:
                best_rank, best = rank, candidate  # type: ignore[assignment]

        if any(skill.phrase for skill in requirement.options):
            worded = self._by_words(requirement)
            if worded is not None and worded[0] > best_rank:
                best_rank, best = worded
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
