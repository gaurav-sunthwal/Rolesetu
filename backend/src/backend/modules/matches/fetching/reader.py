"""Reads the job at a link, trying the free way first and the paid way second."""

import re
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, urlsplit

from backend.modules.errors import service as errors_service
from backend.modules.matches.fetching.job_page import JobPage, is_job_list, read_job_page
from backend.modules.matches.fetching.rendered_fetch import fetch_rendered, is_configured
from backend.modules.matches.fetching.safe_fetch import (
    PASTE_INSTEAD,
    PageBlockedError,
    PageFetchError,
    fetch_page,
)

_INDEED_HOST = re.compile(r"(?:^|\.)indeed\.com$")
_INDEED_JOB_ID = re.compile(r"^[0-9a-f]{16}$")


def page_to_read(url: str) -> str:
    """The address to fetch for a job link.

    Indeed serves an empty page, with no description in it, to its share links
    ("...&from=shareddesktop_copy") and to links copied from search results
    ("/jobs?q=...&vjk=..."). Its plain job address has the whole listing, so
    any Indeed link that names a job is read from there. Other links are
    fetched as they are.
    """
    parts = urlsplit(url)
    if not _INDEED_HOST.search(parts.hostname or ""):
        return url
    query = parse_qs(parts.query)
    job_id = (query.get("jk") or query.get("vjk") or [""])[0]
    if not _INDEED_JOB_ID.match(job_id):
        return url
    return f"https://{parts.hostname}/viewjob?jk={job_id}"


async def load_job_page(
    url: str, may_use_rendered: Callable[[], Awaitable[bool]]
) -> tuple[JobPage, str]:
    """Returns (job, "direct" or "rendered" for how the page was fetched).

    Our own fetch is free and is always tried first. Only when the site blocks
    it, or the page comes back without a job on it, is the paid reader used,
    and then only if `may_use_rendered` agrees (it holds the caller's limits).
    """
    url = page_to_read(url)
    blocked: PageBlockedError | None = None
    markup, page = "", None
    try:
        _, markup = await fetch_page(url)
        page = read_job_page(markup)
    except PageBlockedError as exc:
        blocked = exc

    reader = "direct"
    if page is None and not is_job_list(markup):
        rendered = (
            await fetch_rendered(url) if is_configured() and await may_use_rendered() else None
        )
        if rendered is not None:
            markup, page, reader = rendered, read_job_page(rendered), "rendered"
        elif blocked is not None:
            await _note_failure(url, blocked)
            raise blocked

    if page is None:
        if is_job_list(markup):
            raise PageFetchError(
                "That link is a list of jobs, not one job. Open the job you want and use its link."
            )
        unread = PageFetchError(
            f"We could not find a job description on that page. {PASTE_INSTEAD}"
        )
        await _note_failure(url, unread)
        raise unread
    return page, reader


async def _note_failure(url: str, error: PageFetchError) -> None:
    """A job page we should have been able to read and could not. Recorded by
    site, so the admin panel shows which sites need work. A link that was simply
    wrong (not a job, removed, unsafe) is the visitor's mistake and is not kept.
    """
    await errors_service.record(
        source="job-link",
        level="warning",
        exc=error,
        message=error.detail,
        route=urlsplit(url).hostname,
    )
