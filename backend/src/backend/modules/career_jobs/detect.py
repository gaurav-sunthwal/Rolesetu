"""Works out which platform a careers link belongs to, so a user can add a
company by pasting its jobs page.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class DetectedSource:
    kind: str
    config: dict[str, str]
    # A name to start from; the user can change it.
    suggested_name: str


_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
# What a board's name or a Workday site may look like. The value is put into the
# platform's own web address, so anything else (slashes, dots alone, encoded
# characters) is refused rather than passed on.
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def _name(token: str) -> str:
    return re.sub(r"[-_]+", " ", token).strip().title()


def detect_source(link: str) -> DetectedSource | None:
    parts = urlsplit(link.strip() if "://" in link else f"https://{link.strip()}")
    host = (parts.hostname or "").lower()
    path = [segment for segment in parts.path.split("/") if segment]

    if re.fullmatch(r"[\w-]+\.wd\d+\.myworkdayjobs\.com", host):
        segments = [s for s in path if not _LOCALE.match(s)]
        if not segments or not _TOKEN.match(segments[0]):
            return None
        tenant = host.split(".")[0]
        config = {"host": host, "tenant": tenant, "site": segments[0]}
        return DetectedSource("workday", config, _name(tenant))

    boards = {
        "boards.greenhouse.io": "greenhouse",
        "job-boards.greenhouse.io": "greenhouse",
        "jobs.lever.co": "lever",
        "jobs.ashbyhq.com": "ashby",
        "jobs.smartrecruiters.com": "smartrecruiters",
        "careers.smartrecruiters.com": "smartrecruiters",
    }
    kind = boards.get(host)
    if kind and path and _TOKEN.match(path[0]):
        key = "company" if kind == "smartrecruiters" else "token"
        return DetectedSource(kind, {key: path[0]}, _name(path[0]))
    return None
