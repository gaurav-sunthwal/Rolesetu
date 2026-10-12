"""Reads a job description into the skills it asks for, with no model call.

Skills come from the dictionary. Whether one is required or nice-to-have comes
from the wording around it: the section it sits under ("Preferred
qualifications") or a cue in the same sentence ("... is a plus").
"""

import re
from dataclasses import dataclass, field

from backend.modules.matches.local.catalog import Mention, Skill, find_skills
from backend.modules.matches.local.experience import read_experience
from backend.modules.matches.local.title import find_title

MAX_REQUIRED = 20
MAX_NICE_TO_HAVE = 12
MAX_UNKNOWN = 5

_NICE = re.compile(
    r"nice[- ]to[- ]haves?|good[- ]to[- ]haves?|preferred|bonus(?:es)?|"
    r"(?:is|are|would be|as|considered) an? "
    r"(?:big |huge |strong |definite |added )?(?:plus|advantage)|"
    r"\ba plus\b|\bpluses\b|desirable|desired|ideally|advantageous|optional(?:ly)?|"
    r"not (?:required|mandatory|a must)|would be (?:great|nice|helpful)|brownie points|"
    r"extra credit|helpful but|familiarity with .* (?:helps|is helpful)",
    re.IGNORECASE,
)
_REQUIRED_HEADING = re.compile(
    r"^(?:requirements?|required(?: skills| qualifications)?|must[- ]haves?|qualifications|"
    r"minimum qualifications|basic qualifications|what you(?:'ll| will)? (?:need|bring|do)|"
    r"what we(?:'re| are) looking for|who you are|you have|you should have|responsibilities|"
    r"key responsibilities|about the role|the role|skills(?: required| and experience)?|"
    r"your (?:profile|skills|experience)|technical skills|tech stack|our stack|role overview|"
    r"job description|what you(?:'ll| will) be doing|experience)$",
    re.IGNORECASE,
)
_IGNORED_HEADING = re.compile(
    r"^(?:benefits|perks(?: and benefits)?|what we offer|why join(?: us)?|"
    r"about (?:us|the company|company)|who we are|our (?:company|mission|values|story)|"
    r"compensation|salary|equal opportunity.*|who can apply|deadline|number of openings|"
    r"how to apply|interview process|hiring process|diversity.*|location|working hours)$",
    re.IGNORECASE,
)
_EXAMPLES_BEFORE = re.compile(
    r"(?:e\.g\.?,?|such as|like|for example|for instance|one of|either|any of|"
    r"at least one of|one or more of|similar to)\s*[:(]?\s*$",
    re.IGNORECASE,
)
_LIST_JOIN = re.compile(r"^\s*(?:,|/|,?\s*(?:or|and/or))\s*$", re.IGNORECASE)
_HAS_OR = re.compile(r"\bor\b", re.IGNORECASE)
# Tool-like words the dictionary does not know: "Temporal.io", "LangSmith", "gRPC2".
_UNKNOWN_TOOL = re.compile(
    r"(?<![A-Za-z0-9.])(?:[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+|[A-Za-z][A-Za-z0-9]*\.(?:js|io|ai|py))"
    r"(?![A-Za-z0-9])"
)
_MAX_TOOL_NAME = 24
_NOT_A_TOOL = frozenset(
    {
        "linkedin", "youtube", "whatsapp", "iphone", "ipad", "macos", "devops", "ecommerce",
        "javascript", "typescript", "powerpoint", "wordpress", "facebook", "instagram",
        "tiktok", "mckinsey", "deloitte", "paypal", "github", "gitlab",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Requirement:
    """One thing the job asks for. Several options means "any one of these"."""

    options: tuple[Skill, ...]
    required: bool

    @property
    def name(self) -> str:
        return " or ".join(option.name for option in self.options)


@dataclass
class ParsedJob:
    role: str | None = None
    company: str | None = None
    min_years: int | None = None
    requirements: list[Requirement] = field(default_factory=list)


def _sentences(line: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?;])\s+(?=[A-Z(])", line) if part.strip()]


def _groups(sentence: str, mentions: list[Mention]) -> list[tuple[Skill, ...]]:
    """Splits the skills in a sentence into requirements. Skills offered as
    alternatives ("Jest or Vitest", "a cloud such as AWS, GCP") become one.
    """
    if not mentions:
        return []
    runs: list[list[Mention]] = [[mentions[0]]]
    joined_by_or: list[bool] = [False]
    for previous, current in zip(mentions, mentions[1:], strict=False):
        between = sentence[previous.end : current.start]
        if _LIST_JOIN.match(between):
            runs[-1].append(current)
            joined_by_or[-1] = joined_by_or[-1] or bool(_HAS_OR.search(between))
        else:
            runs.append([current])
            joined_by_or.append(False)

    groups: list[tuple[Skill, ...]] = []
    for run, has_or in zip(runs, joined_by_or, strict=True):
        skills = tuple(dict.fromkeys(mention.skill for mention in run))
        examples = bool(_EXAMPLES_BEFORE.search(sentence[: run[0].start]))
        same_family = len({skill.group for skill in skills}) == 1 and skills[0].group is not None
        slash_only = all(
            "/" in sentence[a.end : b.start] for a, b in zip(run, run[1:], strict=False)
        )
        if len(skills) > 1 and (has_or or examples or (slash_only and same_family)):
            groups.append(skills)
        else:
            groups.extend((skill,) for skill in skills)
    return groups


def _unknown_tools(sentence: str, mentions: list[Mention]) -> list[Skill]:
    """Tool names the dictionary lacks, taken only from a sentence that is
    already listing technologies, so ordinary capitalised words are not picked up.
    """
    if not mentions:
        return []
    taken = [(mention.start, mention.end) for mention in mentions]
    found: list[Skill] = []
    for match in _UNKNOWN_TOOL.finditer(sentence):
        if any(start < match.end() and match.start() < end for start, end in taken):
            continue
        word = match.group(0)
        # Longer than any real tool name: page text with its spaces lost.
        if len(word) > _MAX_TOOL_NAME:
            continue
        if word.lower() in _NOT_A_TOOL:
            continue
        found.append(Skill(name=word))
    return found


def parse_job(jd_text: str, extra_names: tuple[str, ...] = (), url: str | None = None) -> ParsedJob:
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    job = ParsedJob()

    stated = read_experience(jd_text)
    if stated.source == "stated" and stated.min_years and stated.min_years >= 1:
        job.min_years = int(stated.min_years)

    seen: dict[Skill, int] = {}
    unknown_count = 0
    mode = "required"
    for line in lines:
        heading = re.sub(r"[^A-Za-z' /&-]+", " ", line).strip(" :-").strip()
        if len(heading.split()) <= 8 and not line.rstrip().endswith((".", ",")):
            if _IGNORED_HEADING.match(heading):
                mode = "ignored"
                continue
            if _NICE.fullmatch(heading) or (
                _NICE.search(heading) and len(heading.split()) <= 5 and ":" not in line.rstrip(":")
            ):
                mode = "nice"
                continue
            if _REQUIRED_HEADING.match(heading):
                mode = "required"
                continue
        if mode == "ignored":
            continue

        for sentence in _sentences(line):
            mentions = find_skills(sentence, extra_names)
            required = mode == "required" and not _NICE.search(sentence)
            groups = _groups(sentence, mentions)
            for tool in _unknown_tools(sentence, mentions):
                if unknown_count < MAX_UNKNOWN and tool not in seen:
                    groups.append((tool,))
                    unknown_count += 1
            for group in groups:
                options = tuple(skill for skill in group if skill not in seen)
                if not options:
                    # Mentioned again: a later "required" outranks an earlier "nice to have".
                    if required:
                        for skill in group:
                            index = seen[skill]
                            job.requirements[index] = Requirement(
                                job.requirements[index].options, required=True
                            )
                    continue
                for skill in options:
                    seen[skill] = len(job.requirements)
                job.requirements.append(Requirement(options=options, required=required))

    required_items = [item for item in job.requirements if item.required][:MAX_REQUIRED]
    nice_items = [item for item in job.requirements if not item.required][:MAX_NICE_TO_HAVE]
    job.requirements = required_items + nice_items
    job.role, job.company = find_title(
        jd_text, lines, url, [skill for item in job.requirements for skill in item.options]
    )
    return job
