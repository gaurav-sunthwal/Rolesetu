"""Decides what a job-related email is, from its wording alone. No model is
called: these mails are written from templates, and templates are regular.

The body is looked at here and then dropped. Only the sender, subject, date
and the result of this file are ever stored.
"""

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["applied", "rejected", "interview", "assessment", "offer", "unclear"]

# Systems companies send hiring mail through. Mail from these is about a job
# even when its wording matches no rule.
_HIRING_SYSTEMS = re.compile(
    r"greenhouse|lever\.co|ashbyhq|myworkday|workday|workable|smartrecruiters|icims|jobvite|"
    r"teamtailor|recruitee|bamboohr|zohorecruit|keka\.com|darwinbox|freshteam|naukri|"
    r"internshala|linkedin|indeed|wellfound|instahyre|cutshort|unstop|foundit|hirist|"
    r"glassdoor|hackerrank|hackerearth|codility|mettl",
    re.IGNORECASE,
)
# The ones a company uses to write to candidates directly. A mail from these
# that fits no rule is still worth a look, so it is kept as "unclear".
_COMPANY_SYSTEMS = re.compile(
    r"greenhouse|lever\.co|ashbyhq|myworkday|workday|workable|smartrecruiters|icims|jobvite|"
    r"teamtailor|recruitee|bamboohr|zohorecruit|keka\.com|darwinbox|freshteam",
    re.IGNORECASE,
)
_JOB_BOARDS = re.compile(
    r"^(?:linkedin|naukri(?:\.com)?(?: campus)?|internshala|indeed(?: apply)?|wellfound|"
    r"instahyre|cutshort|unstop|"
    r"foundit|hirist|glassdoor|greenhouse|lever|workday|ashby|workable|smartrecruiters|"
    r"hackerrank|hackerearth|codility|google|gmail|mailer[- ]daemon)$",
    re.IGNORECASE,
)
_ABOUT_A_JOB = re.compile(
    r"application|applied|applying|position|\brole\b|candidat|interview|recruit|hiring|"
    r"talent|career|\bjob\b|internship|opening|assessment|coding (?:test|challenge)|"
    r"shortlist|offer letter",
    re.IGNORECASE,
)
# Alerts and marketing from job sites: about jobs, but not about *your* application.
_NOT_YOURS = re.compile(
    r"jobs? (?:alert|for you|matching|recommend)|new jobs?\b|recommended (?:jobs|for you)|"
    r"\d+\+? (?:new )?(?:jobs|openings|internships)|apply now|hiring now|jobs you may|"
    r"similar jobs|digest|newsletter|webinar|\bcourse\b|profile (?:view|was viewed)|"
    r"who viewed|complete your profile|update your (?:profile|resume)|is hiring|are hiring|"
    r"top (?:jobs|picks)|trending|invitation to apply|you may be a (?:good )?fit|"
    r"appeared in \d+ search|(?:complete|finish|continue|resume) your application|"
    r"get your application ready|application (?:is )?incomplete|draft application|"
    r"contest|hackathon|\bquiz\b|starts (?:today|tomorrow|in \d)|\d+ (?:hrs?|hours?|days?) "
    r"(?:to|left)|last (?:chance|day)|register (?:now|today)|registration",
    re.IGNORECASE,
)

# An offer has to be said outright. "If you receive an offer" in an
# acknowledgement, or a company "offering" something, is not one.
_OFFER = re.compile(
    r"(?:pleased|happy|delighted|excited|thrilled) to (?:offer you|extend (?:you )?an offer|"
    r"make you an offer)|(?:attached|enclosed|find) (?:is |please find )?your offer letter|"
    r"offer of employment|we would like to offer you the (?:position|role)|"
    r"congratulations.{0,80}(?:you have been|you are|you've been) selected",
    re.IGNORECASE | re.DOTALL,
)
_OFFER_SUBJECT = re.compile(r"\boffer letter\b|\bjob offer\b|offer of employment", re.IGNORECASE)
_REJECTED = re.compile(
    r"unfortunately|regret to inform|not (?:be )?(?:moving|proceeding|progressing|going) "
    r"(?:forward|ahead|further)|not (?:been )?(?:selected|shortlisted)|(?:decided|chosen) to "
    r"(?:move forward|proceed|go(?: ahead)?|continue) with (?:other|another)|"
    r"will not be (?:moving|proceeding|progressing)|unable to (?:offer|move forward|proceed)|"
    r"not (?:a|the right) (?:fit|match)|position has been (?:filled|closed)|"
    r"pursu(?:e|ing) other candidates|won't be (?:moving|proceeding)|"
    r"other candidates whose|not (?:successful|able to take your application)",
    re.IGNORECASE,
)
_INTERVIEW = re.compile(
    r"schedule (?:an? |your |the )?(?:interview|call|chat|conversation)|"
    r"interview (?:invitation|invite|scheduled|slot|round|confirmation|details)|"
    r"invit(?:e|ing) you (?:to|for) (?:an? |the )?(?:interview|call|chat|discussion)|"
    r"would (?:like|love) to (?:speak|chat|talk|interview|connect) with you|"
    r"availability for (?:an? |the )?(?:interview|call)|(?:next|second|final|technical|hr) "
    r"(?:interview|round)|you(?:'ve| have) been shortlisted|shortlisted for|"
    r"has been shortlisted|screening (?:round|call|interview)|round invitation|"
    r"interview invite",
    re.IGNORECASE,
)
_ASSESSMENT = re.compile(
    r"assessment|coding (?:test|challenge|round)|online test|take[- ]home|"
    r"(?:complete|submit) (?:the|your|this) (?:assignment|task|test)|aptitude test|"
    r"hackerrank|hackerearth|codility|technical (?:test|challenge)",
    re.IGNORECASE,
)
_APPLIED = re.compile(
    r"thank(?:s| you) for (?:applying|your application|your interest|submitting)|"
    r"application (?:has been |was |is )?(?:received|submitted|sent|successful)|"
    r"(?:we(?:'ve| have)|we) received your (?:application|resume|cv)|successfully applied|"
    r"your application (?:to|for|at|with)|you(?:'ve| have)? applied (?:to|for|at)|"
    r"application confirmation|received your application|applied (?:on|to|for)",
    re.IGNORECASE,
)

_ROLE_WORD = re.compile(
    r"\b(developer|engineer|programmer|architect|designer|analyst|scientist|manager|"
    r"consultant|specialist|administrator|tester|intern|internship|lead|officer|executive|"
    r"associate|sde|swe|devops|researcher|writer|marketer|recruiter|trainee)\b",
    re.IGNORECASE,
)
# "... application to Acme", "... at Acme", "... with Acme Corp -"
_COMPANY_IN_SUBJECT = re.compile(
    r"\b(?:at|to|with|from|joining)\s+(?:the\s+)?([A-Z0-9][A-Za-z0-9&.'’-]*(?:\s+[A-Z0-9&][A-Za-z0-9&.'’-]*){0,4})"
)
_ROLE_PATTERNS = (
    # "for the Software Engineer position", "for React Native Developer role at ..."
    re.compile(
        r"\b(?:for|as)\s+(?:the|an?|our)?\s*(?:position|role|post)?\s*(?:of\s+)?"
        r"([A-Z][\w/&+.#-]*(?:\s+[\w/&+.#()-]+){0,6}?)"
        r"(?=\s+(?:position|role|opening|job|vacancy)\b|\s+(?:at|with|in)\b|\s*[-–|:!.,(]|$)"
    ),
    # "Indeed Application: Frontend Engineer"
    re.compile(r"\bapplication:\s*([A-Z][\w/&+.#,-]*(?:\s+[\w/&+.#(),-]+){0,6}?)(?=\s*[-–|:]|$)"),
    # "Software Engineer - Application received", "Application: Software Engineer"
    re.compile(r"(?:^|[:|–-]\s*)([A-Z][\w/&+.#-]*(?:\s+[\w/&+.#()-]+){0,6}?)(?=\s*[-–|:]|$)"),
)
_SENDER_NOISE = re.compile(
    r"\b(?:careers?|recruit(?:ing|ment|er)?|talent(?: acquisition)?|hiring(?: team)?|"
    r"hr|human resources|people(?: team)?|team|jobs?|notifications?|no[- ]?reply|"
    r"via .+|at .+|support|info|hello|mail(?:er)?|updates?)\b",
    re.IGNORECASE,
)
_GENERIC_DOMAINS = frozenset(
    {"gmail", "googlemail", "outlook", "hotmail", "yahoo", "icloud", "proton", "protonmail", "zoho"}
)
_LEGAL = re.compile(
    r"[,.]?\s+\b(?:pvt|private|ltd|limited|inc|llc|llp|corp|corporation|gmbh|co)\b\.?", re.I
)


@dataclass(frozen=True)
class Classified:
    kind: Kind
    company: str | None
    role: str | None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -–|:,.!")


def _named_in(text: str) -> str | None:
    for match in _COMPANY_IN_SUBJECT.finditer(text):
        name = _clean(_LEGAL.sub("", match.group(1)))
        if len(name) >= 2 and not _ROLE_WORD.search(name) and not _JOB_BOARDS.match(name):
            return name
    return None


def _company(subject: str, sender_name: str, sender_email: str, body: str) -> str | None:
    domain = sender_email.rsplit("@", 1)[-1].lower()
    parts = [part for part in domain.split(".") if part not in ("mail", "email", "careers", "jobs")]
    root = parts[-2] if len(parts) >= 2 else ""
    from_domain = (
        root.capitalize()
        if root and root not in _GENERIC_DOMAINS and not _HIRING_SYSTEMS.search(root)
        else None
    )
    # A reply in a conversation is from a person: their name is not the
    # company, but their work address usually is.
    if re.match(r"\s*(?:re|fwd?)\s*:", subject, re.IGNORECASE):
        return from_domain

    found = _named_in(subject)
    if found:
        return found
    # "Priya from Swiggy" is Swiggy; "Razorpay Careers" is Razorpay.
    person_from = re.search(r"\bfrom\s+(.+)$", sender_name, re.IGNORECASE)
    raw = person_from.group(1) if person_from else sender_name
    name = _clean(_LEGAL.sub("", _SENDER_NOISE.sub(" ", raw)))
    if len(name) >= 2 and not _JOB_BOARDS.match(name) and "@" not in name:
        return name
    # A mail sent through a hiring system names the company only in its text.
    found = _named_in(body[:600])
    if found:
        return found
    return from_domain


def _role(subject: str, body: str) -> str | None:
    for text in (subject, body[:600]):
        for pattern in _ROLE_PATTERNS:
            for match in pattern.finditer(text):
                role = _clean(match.group(1))
                if 3 <= len(role) <= 70 and _ROLE_WORD.search(role):
                    return role
    return None


def classify(subject: str, sender_name: str, sender_email: str, body: str) -> Classified | None:
    """What this mail says about an application, or None when it is not about
    one (and so is not kept at all).
    """
    text = f"{subject}\n{body[:4000]}"
    from_hiring_system = _HIRING_SYSTEMS.search(sender_email) is not None
    if _NOT_YOURS.search(subject):
        return None
    if not from_hiring_system and not _ABOUT_A_JOB.search(f"{text}\n{sender_name}"):
        return None

    kind: Kind
    if _OFFER_SUBJECT.search(subject) or _OFFER.search(text):
        kind = "offer"
    elif _REJECTED.search(text):
        kind = "rejected"
    # A confirmation often lists the steps to come ("you may be invited to an
    # interview"), so a subject that says "received" settles it first.
    elif _APPLIED.search(subject):
        kind = "applied"
    elif _INTERVIEW.search(text):
        kind = "interview"
    elif _ASSESSMENT.search(text):
        kind = "assessment"
    elif _APPLIED.search(text):
        kind = "applied"
    elif _COMPANY_SYSTEMS.search(sender_email) and _ABOUT_A_JOB.search(text):
        kind = "unclear"
    else:
        return None

    return Classified(
        kind=kind,
        company=_company(subject, sender_name, sender_email, body),
        role=_role(subject, body),
    )
