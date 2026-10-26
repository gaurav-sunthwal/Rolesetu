"""Whether a job is remote, hybrid or on-site, from what its posting says.

Single words are not enough: "hybrid cloud", "remote support" and
"onsite-offshore teams" are about the work, not where it is done, and "work
from anywhere for 8 weeks a year" is a perk. So only phrases that describe the
arrangement count. When a posting says nothing we can trust, the answer is
"not_stated": we never guess on-site just because remote is not mentioned.
"""

import re
from typing import Literal

WorkMode = Literal["remote", "hybrid", "onsite", "not_stated"]

_ONSITE_WORDS = r"(?:on-?site|in-office|office-based|work from office|wfo|office)"
# "Work model: Hybrid", "Workplace type - Remote", "Work arrangement: Work from office".
_LABEL = (
    r"(?:work(?:ing)?\s*(?:model|mode|type|arrangement|style)|workplace\s*type|location\s*type)"
    r"\s*[:\-–]\s*"
)
# IBM tags each job "<area> Hybrid Professional <city>".
_IBM_TAG = r"\b{mode}\s+(?:professional|entry level|internship|executive)\b"
_FEW_DAYS = r"(?:one|two|three|four|[1-4])(?:\s*(?:-|to|or)\s*(?:two|three|four|[1-4]))?"

_HYBRID = re.compile(
    "|".join(
        (
            r"#li-hybrid\b",
            r"\bhybrid\s+(?:work|working|model|mode|role|position|job|opportunity|arrangement|"
            r"schedule|set-?up|policy|basis)\b",
            _LABEL + r"hybrid\b",
            _IBM_TAG.format(mode="hybrid"),
            # "2-3 days a week in the office", "in the Pune office three days a week".
            _FEW_DAYS + r"\s+days?\s+(?:a|per|each)\s+week\s+(?:in|at|from)\s+(?:the\s+)?"
            r"(?:\w+\s+){0,2}office\b",
            r"\b(?:office|in-person|on-?site)\b[^.\n]{0,40}?\b"
            + _FEW_DAYS
            + r"\s+days?\s+(?:a|per|each)\s+week\b",
        )
    ),
    re.I,
)
_REMOTE = re.compile(
    "|".join(
        (
            r"#li-remote\b",
            r"\b(?:fully|100%|completely|permanently)\s+remote\b",
            r"\bremote-first\b",
            r"\bremote\s+(?:role|position|job|opportunity)\b",
            r"\b(?:role|position|job)\s+is\s+(?:fully\s+)?remote\b",
            _LABEL + r"(?:remote|work from home)\b",
            _IBM_TAG.format(mode="remote"),
        )
    ),
    re.I,
)
_ONSITE = re.compile(
    "|".join(
        (
            r"#li-(?:onsite|office)\b",
            r"\bwork from office\b",
            r"\bwfo\b",
            r"\b(?:fully|100%|completely)\s+(?:on-?site|in-office|office-based)\b",
            r"\b(?:on-?site|in-office|office-based)\s+(?:role|position|job|project|opportunity)\b",
            r"\bon-?site\s+presence\b",
            r"\b(?:five|5)\s+days?\s+(?:a|per|each)\s+week\s+(?:in|at|from)\s+(?:the\s+)?office\b",
            _LABEL + _ONSITE_WORDS + r"\b",
            _IBM_TAG.format(mode="on-?site"),
        )
    ),
    re.I,
)
# "We offer everything from in-office to fully remote" lists options, not this job's.
_RANGE = re.compile(
    r"\bfrom\s+(?:in-office|on-?site|office)\b[^.\n]{0,80}?\bto\s+(?:fully\s+)?remote\b", re.I
)
# "This is not a remote role" says on-site, not remote.
_NOT_REMOTE = re.compile(r"\b(?:not|no)\s+(?:an?\s+)?(?:fully\s+)?remote\b", re.I)
_LOCATION_REMOTE = re.compile(r"\bremote\b|work from home|\bwfh\b", re.I)
_LOCATION_HYBRID = re.compile(r"\bhybrid\b", re.I)
_LOCATION_ONSITE = re.compile(r"\bon-?site\b|\bin-office\b|work from office|\bwfo\b", re.I)
# A mode tagged onto a title: "Engineer (Remote)", "Analyst - Hybrid", "SRE | WFH".
# Not any word in it: "Hybrid Cloud Architect" and "Remote Sensing Lead" are jobs.
_TITLE_TAG = re.compile(
    r"(?:[(\[]\s*(?P<a>remote|hybrid|on-?site|wfh|wfo)\s*[)\]]"
    r"|[-–|,/]\s*(?P<b>remote|hybrid|on-?site|wfh|wfo)\s*$)",
    re.I,
)
_TAG_MODE: dict[str, WorkMode] = {
    "remote": "remote",
    "wfh": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "wfo": "onsite",
}


def work_mode_of(*, title: str, location: str, description: str) -> WorkMode:
    # The location is short and only about where the job is, so one word there
    # is trusted; the description needs a full phrase.
    if _LOCATION_HYBRID.search(location):
        return "hybrid"
    if _LOCATION_REMOTE.search(location):
        return "remote"
    if _LOCATION_ONSITE.search(location):
        return "onsite"
    tag = _TITLE_TAG.search(title)
    if tag:
        return _TAG_MODE[(tag.group("a") or tag.group("b")).lower()]

    description = _RANGE.sub(" ", description)
    if _HYBRID.search(description):
        return "hybrid"
    if _NOT_REMOTE.search(description):
        return "onsite"
    if _REMOTE.search(description):
        return "remote"
    if _ONSITE.search(description):
        return "onsite"
    return "not_stated"
