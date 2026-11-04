"""A stable name for a job, read from its link, so the same job is recognised
however its page text came out this time.

The text a page shows changes between visits ("Reposted 2 hours ago", a
description collapsed behind "see more"), and each change used to look like a
new job and cost a new model call. The job's id in its link does not change.
Only sites whose links carry a real job id are named here: guessing an id from
any other link could hand one job's result to another job.
"""

import re

_SITES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # /jobs/view/4460038564/, /jobs/view/data-engineer-at-x-4460038564, ?currentJobId=4460038564
    # (links are lower-cased before matching)
    (
        "linkedin",
        re.compile(
            r"linkedin\.com.*?(?:/jobs/view/(?:[^/?#]*?-)?(\d{6,})|[?&]currentjobid=(\d{6,}))"
        ),
    ),
    ("indeed", re.compile(r"indeed\.[a-z.]+/.*?[?&](?:jk|vjk)=([0-9a-f]{8,})")),
    ("naukri", re.compile(r"naukri\.com/job-listings-[^?#]*?-(\d{6,})(?:[/?#]|$)")),
    ("internshala", re.compile(r"internshala\.com/(?:internship|job)/detail/[^?#]*?(\d{6,})")),
    (
        "greenhouse",
        re.compile(r"(?:greenhouse\.io/[^/?#]+/jobs/(\d+)|[?&]gh_jid=(\d+))"),
    ),
    ("lever", re.compile(r"jobs\.lever\.co/[^/?#]+/([0-9a-f-]{36})")),
)


def job_key(url: str | None) -> str | None:
    """The job's id, as "linkedin:4460038564", for a known site's link; else None."""
    if not url:
        return None
    for site, pattern in _SITES:
        found = pattern.search(url.lower())
        if found:
            job_id = next(group for group in found.groups() if group)
            return f"{site}:{job_id.lower()}"
    return None
