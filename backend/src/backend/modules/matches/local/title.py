"""Works out a job's title and company when the pasted text does not lead with them.

People often paste only the body of a listing ("About the job", "Key
Responsibilities"), so the title is looked for in several places, most reliable
first: a labelled line, the opening lines, a phrase in the text, the listing's
link, and finally a title inferred from the skills the job asks for.
"""

import re
from urllib.parse import unquote, urlparse

from backend.modules.matches.local.catalog import Skill

_TITLE_WORD = re.compile(
    r"\b(?:engineer|developer|intern|manager|analyst|designer|architect|consultant|lead|"
    r"scientist|specialist|administrator|programmer|tester|devops|sre|director|associate|"
    r"officer|researcher|writer|marketer|recruiter|executive|head)\b",
    re.IGNORECASE,
)
_HEADING_START = re.compile(
    r"^(?:about|selected|key|role overview|responsibilit|description|requirements?|"
    r"what you|who you|summary|overview|job description|skills?)\b",
    re.IGNORECASE,
)
_LABELLED = re.compile(
    r"^(?:job\s+title|job\s+role|title|role|position|designation|profile)\s*[:\-–]\s*(.+)$",
    re.IGNORECASE,
)
_COMPANY_LABELLED = re.compile(
    r"^(?:company|company\s+name|organisation|organization|employer)\s*[:\-–]\s*(.+)$",
    re.IGNORECASE,
)
# "As a React Native engineer (iOS) intern at Humanity Founders, you will ..."
_IN_SENTENCE = re.compile(
    r"\b(?i:as an?|for an?|hiring an?|looking for an?|seeking an?|join(?: us| our team)? as an?|"
    r"role of an?|position of an?|opening for an?)\s+"
    r"(?P<role>[A-Za-z][A-Za-z0-9 ()/+.#&-]{2,70}?)"
    r"(?:\s+(?:at|with|@)\s+(?P<company>[A-Z][A-Za-z0-9&.' -]{1,60}?))?"
    r"(?=\s*(?:,|\.|;|\s+(?:you|we|who|to|in|for|and|is|will)\b))",
)
_SLUG_NOISE = re.compile(
    r"^(?:work-from-home|work-from-office|remote|fresher|freshers|part-time|full-time|hybrid|"
    r"onsite|on-site|urgent|hiring|paid|unpaid|wfh)-",
    re.IGNORECASE,
)
_ACRONYMS = {
    "ai": "AI", "ml": "ML", "ui": "UI", "ux": "UX", "ios": "iOS", "qa": "QA", "php": "PHP",
    "sql": "SQL", "seo": "SEO", "api": "API", "hr": "HR", "it": "IT", "aws": "AWS", "sde": "SDE",
    "devops": "DevOps", "javascript": "JavaScript", "typescript": "TypeScript", "nodejs": "Node.js",
    "reactjs": "React", "dotnet": ".NET", "ii": "II", "iii": "III", "llm": "LLM", "nlp": "NLP",
    "pvt": "Pvt", "ltd": "Ltd", "llp": "LLP", "llc": "LLC",
}  # fmt: skip

# Skills that point at a kind of role, used only when nothing else names one.
_FAMILIES: tuple[tuple[str, frozenset[str]], ...] = (
    ("React Native Developer", frozenset({"React Native", "Expo"})),
    ("Flutter Developer", frozenset({"Flutter", "Dart"})),
    ("Android Developer", frozenset({"Android", "Kotlin", "Jetpack Compose", "Android Studio"})),
    ("iOS Developer", frozenset({"iOS", "Swift", "SwiftUI", "UIKit", "Xcode"})),
    (
        "Machine Learning Engineer",
        frozenset({"Machine learning", "Deep learning", "PyTorch", "TensorFlow", "LLMs", "NLP",
                   "Computer vision", "scikit-learn", "RAG", "LangChain"}),
    ),
    (
        "Data Analyst",
        frozenset({"pandas", "Tableau", "Power BI", "Looker", "Excel", "Statistics",
                   "Data analysis", "Data visualization", "A/B testing", "dbt"}),
    ),
    (
        "DevOps Engineer",
        frozenset({"Kubernetes", "Terraform", "Ansible", "Jenkins", "Prometheus", "Grafana",
                   "CloudFormation"}),
    ),
    (
        "UI/UX Designer",
        frozenset({"Figma", "Sketch", "Adobe XD", "Prototyping", "User research", "UI/UX",
                   "Design systems"}),
    ),
)  # fmt: skip
# The first four families (the mobile frameworks) are specific enough alone.
_SPECIFIC_FAMILIES = 4
_FRONTEND = frozenset(
    {"React", "Vue", "Angular", "Svelte", "Next.js", "HTML", "CSS", "Tailwind CSS", "Redux",
     "JavaScript", "TypeScript", "Responsive design"}
)  # fmt: skip
_BACKEND = frozenset(
    {"Node.js", "Express", "NestJS", "Django", "Flask", "FastAPI", "Spring", "Ruby on Rails",
     "Laravel", "ASP.NET", "PHP", "PostgreSQL", "MySQL", "MongoDB", "SQL", "REST APIs",
     "Microservices", "Redis", "Java", "Python", "Go"}
)  # fmt: skip


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -–—|:,.")


def _capitalise_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _from_lines(lines: list[str]) -> tuple[str | None, str | None]:
    role = company = None
    for line in lines[:20]:
        labelled = _LABELLED.match(line)
        if labelled and role is None and len(labelled.group(1).split()) <= 10:
            role = _tidy(labelled.group(1))
        named = _COMPANY_LABELLED.match(line)
        if named and company is None and len(named.group(1).split()) <= 8:
            company = _tidy(named.group(1))
    if role:
        return role, company

    for line in lines[:3]:
        text = _tidy(line)
        if not text or len(text.split()) > 8 or line.rstrip().endswith((".", ":")) or ":" in text:
            continue
        if _HEADING_START.match(text):
            continue
        if not _TITLE_WORD.search(text):
            continue
        parts = re.split(r"\s+(?:at|@)\s+|\s+[-–—|]\s+", text, maxsplit=1)
        role = re.sub(r"\s*\(.*?\)\s*$", "", parts[0]).strip()
        if len(parts) == 2:
            candidate = _tidy(re.sub(r"\s*\(.*?\)\s*$", "", parts[1]))
            if candidate and len(candidate.split()) <= 5 and not _TITLE_WORD.search(candidate):
                company = company or candidate
        return (role or None), company
    return None, company


def _from_sentence(text: str) -> tuple[str | None, str | None]:
    for match in _IN_SENTENCE.finditer(text[:3000]):
        role = _tidy(match.group("role"))
        if _TITLE_WORD.search(role) and len(role.split()) <= 8:
            company = match.group("company")
            return _capitalise_first(role), (_tidy(company) if company else None)
    return None, None


def _words(slug: str) -> str:
    words = [word for word in slug.split("-") if word]
    return " ".join(_ACRONYMS.get(word.lower(), word.capitalize()) for word in words)


def _from_url(url: str | None) -> tuple[str | None, str | None]:
    """Listing links usually spell the job out:
    .../android-app-development-internship-at-infinexa-learning-solutions1790573663
    """
    if not url:
        return None, None
    path = unquote(urlparse(url).path).rstrip("/")
    slug = re.sub(r"\d{5,}$", "", path.rsplit("/", 1)[-1]).strip("-")
    if "-at-" not in slug or "," in slug or not re.search(r"[a-z]", slug, re.IGNORECASE):
        return None, None
    role_slug, company_slug = slug.rsplit("-at-", 1)
    while _SLUG_NOISE.match(role_slug):
        role_slug = _SLUG_NOISE.sub("", role_slug, count=1)
    role_slug = re.sub(r"-(?:job|jobs|vacancy|opening)$", "", role_slug, flags=re.IGNORECASE)
    role, company = _words(role_slug), _words(company_slug)
    if not role or len(role.split()) > 10:
        return None, None
    return role, (company if company and len(company.split()) <= 8 else None)


def _inferred(text: str, skills: list[Skill]) -> str | None:
    """A plain description of the kind of role, from what the job asks for."""
    names = {skill.name for skill in skills}
    lowered = text.lower()
    front, back = len(names & _FRONTEND), len(names & _BACKEND)
    title: str | None = None
    # Most specific first. A mobile framework names the role on its own. Then
    # the job's own wording ("full stack"). Broader families need two signs, so
    # one stray word ("dashboards") does not decide it.
    specific, broad = _FAMILIES[:_SPECIFIC_FAMILIES], _FAMILIES[_SPECIFIC_FAMILIES:]
    title = next((name for name, family in specific if names & family), None)
    if title is None and re.search(
        r"\bfull[\s-]?stack\b|\bfront[\s-]?end(?:,| and) back[\s-]?end\b", lowered
    ):
        title = "Full Stack Developer"
    if title is None:
        title = next((name for name, family in broad if len(names & family) >= 2), None)
    if title is None:
        if front >= 2 and back >= 2:
            title = "Full Stack Developer"
        elif front and front >= back:
            title = "Frontend Developer"
        elif back:
            title = "Backend Developer"
    if title and re.search(r"\bintern(?:s|ship)?\b", lowered):
        title = f"{title} Intern"
    return title


def find_title(
    jd_text: str, lines: list[str], url: str | None, skills: list[Skill]
) -> tuple[str | None, str | None]:
    """Returns (role, company). Each source fills only what the ones before left blank."""
    role, company = _from_lines(lines)
    if not (role and company):
        found_role, found_company = _from_sentence(jd_text)
        role, company = role or found_role, company or found_company
    if not (role and company):
        found_role, found_company = _from_url(url)
        role, company = role or found_role, company or found_company
    return (role or _inferred(jd_text, skills)), company
