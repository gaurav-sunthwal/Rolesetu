"""Writes answers to the questions every application asks in its own words ("What
interests you about working for this company?", "Write a note to the founder"),
from the user's own profile and the job in front of them. No model call: it costs
nothing, answers at once, and cannot invent anything.

How an answer is put together:

1. The question's kind (why this company, why hire you, about you, note to the
   founder) picks a template of a few sentences.
2. The job's text is searched for skills the profile names, so the answer leads
   with what this job wants and the user can show.
3. The project and the role that best show those skills are picked, and their
   own first sentence is turned into "I built..." or "On X, I...".

Every fact comes from the profile; the job only decides which facts come first
and supplies the company and role names. Text from the job page is never copied
into the answer, so instructions hidden in a posting have nothing to act on.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from backend.modules.profiles.schemas import ExperienceItem, ProfileRead, ProjectItem

PitchKind = Literal["why_company", "why_hire", "about_you", "note_to_founder"]

_KINDS: list[tuple[PitchKind, re.Pattern[str]]] = [
    (
        "note_to_founder",
        re.compile(
            r"\b(?:co-?founders?|founders?|ceo|hiring manager)\b|"
            r"\b(?:note|message) (?:to|for) (?:the )?(?:team|recruiters?)\b|"
            r"\breach out\b|\bstart a conversation\b|\bget in touch\b|\bintroduce yourself to\b",
            re.IGNORECASE,
        ),
    ),
    (
        "why_hire",
        re.compile(
            r"why should (?:we|i|they) (?:hire|select|choose|pick)|"
            r"what makes you (?:a |the )?(?:good|great|right|strong|ideal|best|perfect|unique)|"
            r"why are you (?:a |the )?(?:good|great|right|best|ideal) (?:fit|candidate|match)|"
            r"stand out|why (?:you|should it be you)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "about_you",
        re.compile(
            r"tell (?:us|me) (?:a (?:bit|little) )?about yourself|introduce yourself|"
            r"describe yourself|who are you\b|about you\b",
            re.IGNORECASE,
        ),
    ),
    (
        "why_company",
        re.compile(
            r"why (?:do you want to|would you like to|are you (?:interested|excited|applying)|"
            r"this (?:company|role|job|position|opportunity)|us\b|join|work (?:here|with us|at))|"
            r"what (?:interests|excites|attracts|draws|motivates) you|"
            r"interest(?:ed)? in (?:working|joining|this)|cover letter|motivation for applying",
            re.IGNORECASE,
        ),
    ),
]

# "Write a note to Rahul", "Message for Priya Shah": the name right after "to"/"for".
_ADDRESSEE = re.compile(r"\b(?:note|message|intro|email|pitch)\s+(?:to|for)\s+([A-Z][a-z]{1,20})\b")
_NOT_A_NAME = frozenset({"The", "Our", "Us", "Them", "Your", "This", "Founder", "Team", "Hiring"})

# A line that says what the person did ("Built...", "Build and maintain...").
_DID = re.compile(
    r"^(?:built|build|developed|develop|created|create|designed|design|implemented|implement|"
    r"engineered|led|lead|launched|launch|shipped|ship|architected|integrated|integrate|"
    r"automated|automate|wrote|write|made|deployed|deploy|optimi[sz]ed|optimi[sz]e|reduced|"
    r"improved|migrated|delivered|owned|own|managed|manage|maintained|maintain|scaled|scale|"
    r"added|cut|split|reached|grew|worked|work|set up|contributed|collaborated)\b",
    re.IGNORECASE,
)
_ARTICLE_START = re.compile(r"^(?:an?|the)\s", re.IGNORECASE)
_BULLET = re.compile(r"^[\s•\-–*·▪●]+")


def pitch_kind(question: str) -> PitchKind | None:
    """Which pitch question this is, or None for any other question."""
    for kind, pattern in _KINDS:
        if pattern.search(question):
            return kind
    return None


# "the team at Encord", "join Encord", "why Encord interests you".
_COMPANY_IN_TEXT = re.compile(
    r"\b(?:team at|join|at|why)\s+"
    # Words of a name; a dot only inside one ("Next.ai"), never the one ending a sentence.
    r"([A-Z][\w&\-]*(?:\.[\w]+)*(?:\s+[A-Z][\w&\-]*(?:\.[\w]+)*){0,2})"
)
_NOT_A_COMPANY = frozenset({"The", "Our", "Your", "This", "Least", "All", "Us", "You", "I"})


def company_in(text: str) -> str | None:
    """The company a pop-up names in its heading ("Reach out to the team at Encord")."""
    for match in _COMPANY_IN_TEXT.finditer(text):
        name = match.group(1).rstrip(".")
        if name.split()[0] not in _NOT_A_COMPANY:
            return name
    return None


def addressee(question: str) -> str | None:
    """The first name a note is addressed to, when the question names one."""
    for match in _ADDRESSEE.finditer(question):
        name = match.group(1)
        if name not in _NOT_A_NAME:
            return name
    return None


@dataclass(frozen=True)
class JobContext:
    company: str | None
    role: str | None
    text: str
    founder: str | None = None


@dataclass(frozen=True)
class Composed:
    text: str
    # What the answer was built from, shown so the user sees why it says what it says.
    uses: list[str] = field(default_factory=list)


# ─── Small pieces of English ──────────────────────────────────────────────────


def join_words(items: Sequence[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def with_article(phrase: str) -> str:
    return f"{'an' if phrase[:1].lower() in 'aeiou' else 'a'} {phrase}"


def first_sentence(text: str, limit: int = 180) -> str:
    """The first sentence or bullet of a description, without its bullet mark or end stop."""
    for line in text.splitlines():
        line = _BULLET.sub("", line).strip()
        if line:
            break
    else:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", line, maxsplit=1)[0]
    if len(sentence) > limit:
        cut = sentence[:limit]
        sentence = cut[: max(cut.rfind(","), cut.rfind(" "))] if " " in cut else cut
    return sentence.strip().rstrip(".;:,!")


def _lower_first(text: str) -> str:
    # "Built" becomes "built", but "API" and "React" keep their capitals.
    if len(text) > 1 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


def years_phrase(years: float) -> str | None:
    if years >= 2:
        return f"{int(years)}+ years"
    if years >= 1:
        return "over a year"
    return None


# ─── Choosing what to say ─────────────────────────────────────────────────────


def _mentions(text: str, name: str) -> bool:
    return _first_mention(text, name) is not None


def _first_mention(text: str, name: str) -> int | None:
    escaped = re.escape(name.lower())
    match = re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text)
    return match.start() if match else None


def skill_label(name: str) -> str:
    """'JavaScript (ES6+)' is said as 'JavaScript'."""
    return re.sub(r"\s*\(.*?\)\s*", " ", name).strip()


def _spellings(name: str) -> set[str]:
    """The ways a posting may write a skill: 'React.js' is also 'React', 'Node' is 'Node.js'."""
    label = skill_label(name).lower()
    names = {label}
    if label.endswith(".js") or label.endswith("js"):
        names.add(re.sub(r"\.?js$", "", label))
    return {spelled for spelled in names if len(spelled) >= 2}


def skills_in_job(profile: ProfileRead, job_text: str) -> list[str]:
    """The profile's skills this job names, the ones the job mentions first first."""
    lowered = job_text.lower()
    found: dict[str, int] = {}
    for skill in profile.skills:
        positions = [
            position
            for spelled in _spellings(skill.name)
            if (position := _first_mention(lowered, spelled)) is not None
        ]
        label = skill_label(skill.name)
        if positions and label.lower() not in {name.lower() for name in found}:
            found[label] = min(positions)
    return sorted(found, key=found.__getitem__)


def _lines(description: str) -> list[str]:
    return [line for raw in description.splitlines() if (line := _BULLET.sub("", raw).strip())]


def tagline(description: str) -> str | None:
    """What a project is, when its description opens with a short title line:
    'AI Job Matching Platform & Chrome Extension'."""
    lines = _lines(description)
    if not lines:
        return None
    first = first_sentence(lines[0].split(" | ")[0])
    if not first or _DID.match(first) or len(first.split()) > 12 or len(first.split()) < 2:
        return None
    return first


def best_bullet(description: str, wanted: list[str]) -> str | None:
    """The line saying what the person did that shows the most of what the job wants."""
    did = [line for line in _lines(description) if _DID.match(line)]
    if not did:
        return None
    lowered_wanted = [name.lower() for name in wanted]

    def shows(line: str) -> int:
        return sum(1 for name in lowered_wanted if _mentions(line.lower(), name))

    best = max(did, key=lambda line: (shows(line), -did.index(line)))
    return first_sentence(best)


def _project_score(project: ProjectItem, wanted: set[str], job_text: str) -> float:
    tech = {skill_label(name).lower() for name in project.tech}
    described = project.description.lower()
    named_in_job = sum(1 for name in tech if _mentions(job_text, name))
    shown_by_description = sum(1 for skill in wanted if _mentions(described, skill))
    return 2 * len(tech & wanted) + named_in_job + shown_by_description + (0.5 if described else 0)


def ranked_projects(profile: ProfileRead, wanted: list[str], job_text: str) -> list[ProjectItem]:
    """The profile's projects, the ones that best show what the job wants first."""
    lowered_wanted = {name.lower() for name in wanted}
    lowered_job = job_text.lower()
    return sorted(
        profile.projects,
        key=lambda p: _project_score(p, lowered_wanted, lowered_job),
        reverse=True,
    )


def best_project(profile: ProfileRead, wanted: list[str], job_text: str) -> ProjectItem | None:
    ranked = ranked_projects(profile, wanted, job_text)
    return ranked[0] if ranked else None


def latest_role(profile: ProfileRead) -> ExperienceItem | None:
    if not profile.experience:
        return None
    return max(profile.experience, key=lambda job: (job.end or "9999-12", job.start or ""))


def _a_thing(phrase: str) -> str:
    """'a real-time chat app', 'an AI Job Matching Platform'."""
    return _lower_first(phrase) if _ARTICLE_START.match(phrase) else with_article(phrase)


def project_sentence(project: ProjectItem, wanted: list[str]) -> str:
    """'On Rolesetu, an AI job platform, I launched...', or else
    'I built ChatFlow, a chat app, using React.'"""
    what = tagline(project.description)
    did = best_bullet(project.description, wanted)
    if did:
        named = f"{project.name}, {_a_thing(what)}," if what else f"{project.name},"
        return f"On {named} I {_lower_first(did)}."

    lowered_wanted = {name.lower() for name in wanted}
    tech = sorted(project.tech, key=lambda name: skill_label(name).lower() not in lowered_wanted)
    tech_named = [
        skill_label(name) for name in tech[:3] if not _mentions((what or "").lower(), name)
    ]
    using = f" using {join_words(tech_named)}" if tech_named else ""
    if what:
        return f"I built {project.name}, {_a_thing(what)}{',' if using else ''}{using}."
    return f"I built {project.name}{using}."


def role_sentence(role: ExperienceItem, wanted: list[str]) -> str:
    """'As Software Engineer at Acme, I reduced API latency by 40%.'"""
    did = best_bullet(role.description, wanted)
    if did:
        return f"As {role.title} at {role.company}, I {_lower_first(did)}."
    tense = "work" if role.end is None else "worked"
    return f"I {tense} as {role.title} at {role.company}."


# ─── The answers ──────────────────────────────────────────────────────────────


def compose(
    kind: PitchKind,
    profile: ProfileRead,
    job: JobContext,
    *,
    years: float,
) -> Composed:
    company = (job.company or "").strip() or None
    role = (job.role or "").strip() or None
    in_job = skills_in_job(profile, job.text)
    wanted = in_job[:3]
    skills = wanted or [skill_label(skill.name) for skill in profile.skills[:3]]
    project = best_project(profile, in_job, job.text)
    latest = latest_role(profile)
    span = years_phrase(years)
    first_name = (profile.full_name or "").split(" ")[0] or None

    proof = [
        sentence
        for sentence in (
            project_sentence(project, in_job) if project else None,
            role_sentence(latest, in_job) if latest else None,
        )
        if sentence
    ]
    uses = [*wanted, *([project.name] if project else []), *([latest.company] if latest else [])]

    the_role = f"the {role} role" if role else "this role"
    at_company = f" at {company}" if company else ""
    company_name = company or "your team"
    skill_words = join_words(skills)

    sentences: list[str]
    if kind == "why_company":
        doing = f", the work I've been doing for {span}" if span and wanted else ""
        if wanted:
            opener = (
                f"I'm excited about {the_role}{at_company} because it centres on"
                f" {skill_words}{doing}."
            )
        elif skills:
            opener = (
                f"I'm excited about {the_role}{at_company} and the chance to put my experience"
                f" with {skill_words} to work there."
            )
        else:
            opener = f"I'm excited about {the_role}{at_company} and the chance to contribute there."
        sentences = [opener, *proof, f"I'd love to bring that experience to {company_name}."]

    elif kind == "why_hire":
        for_span = f" from {span} of building" if span else ""
        calls_for = f", which is what {the_role} calls for" if wanted else ""
        sentences = [
            f"I bring hands-on experience with {skill_words}{for_span}{calls_for}."
            if skills
            else f"I'd bring real commitment to {the_role}{at_company}.",
            *proof,
            f"I'm ready to put that to work for {company_name} from day one.",
        ]

    elif kind == "about_you":
        who = f"I'm {first_name}" if first_name else "I'm"
        headline = f", {with_article(profile.headline)}" if profile.headline else ""
        span_part = f" with {span} of experience" if span else ""
        sentences = [
            f"{who}{headline}{span_part}.",
            *([f"I work mostly with {skill_words}."] if skills else []),
            *proof,
            f"I'm now looking for {the_role}{at_company} where I can keep building.",
        ]

    else:  # note_to_founder
        greeting = (
            f"Hi {job.founder}," if job.founder else f"Hi {company} team," if company else "Hi,"
        )
        who = f"I'm {first_name}" if first_name else "I'm a developer"
        headline = f", {with_article(profile.headline)}" if profile.headline and first_name else ""
        span_part = f" with {span} of experience" if span else ""
        if wanted:
            fit = (
                f"{the_role[:1].upper()}{the_role[1:]}{at_company} lines up closely with my work"
                f" in {skill_words}."
            )
        elif role:
            fit = f"I'd love to be considered for {the_role}{at_company}."
        elif skills:
            # Reaching out with no opening in view: say what the user is looking for.
            fit = (
                f"I'm reaching out because I'd love to work with {company_name}, building with"
                f" {skill_words}."
            )
        else:
            fit = f"I'm reaching out because I'd love to work with {company_name}."
        link = profile.links.portfolio or profile.links.github
        sentences = [
            f"{greeting} {who}{headline}{span_part}.",
            fit,
            *proof[:1],
            f"I'd love to talk about how I could help {company_name}."
            + (f" You can see my work at {link}." if link else ""),
        ]

    return Composed(text=" ".join(sentences), uses=list(dict.fromkeys(uses)))


# ─── The user's own answer, reused for another company ───────────────────────

TOKENS = ("{company}", "{role}", "{founder}")


def is_template(answer: str) -> bool:
    return any(token in answer for token in TOKENS)


def fill_template(answer: str, job: JobContext) -> str:
    """The user's saved answer with this job's names in place of the tokens."""
    role = (job.role or "").strip() or "open"
    # "a {role}" stays right for "an AI Engineer".
    answer = re.sub(
        r"\b([Aa])n? \{role\}",
        lambda found: f"{found.group(1)}{'n' if role[:1].lower() in 'aeiou' else ''} {{role}}",
        answer,
    )
    return (
        answer.replace("{company}", (job.company or "").strip() or "your company")
        .replace("{role}", role)
        .replace("{founder}", job.founder or "there")
    )
