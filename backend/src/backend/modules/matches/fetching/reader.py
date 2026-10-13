"""Reads the job at a link, trying the free way first and the paid way second."""

from collections.abc import Awaitable, Callable

from backend.modules.matches.fetching.job_page import JobPage, is_job_list, read_job_page
from backend.modules.matches.fetching.rendered_fetch import fetch_rendered, is_configured
from backend.modules.matches.fetching.safe_fetch import (
    PASTE_INSTEAD,
    PageBlockedError,
    PageFetchError,
    fetch_page,
)


async def load_job_page(
    url: str, may_use_rendered: Callable[[], Awaitable[bool]]
) -> tuple[JobPage, str]:
    """Returns (job, "direct" or "rendered" for how the page was fetched).

    Our own fetch is free and is always tried first. Only when the site blocks
    it, or the page comes back without a job on it, is the paid reader used,
    and then only if `may_use_rendered` agrees (it holds the caller's limits).
    """
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
            raise blocked

    if page is None:
        if is_job_list(markup):
            raise PageFetchError(
                "That link is a list of jobs, not one job. Open the job you want and use its link."
            )
        raise PageFetchError(f"We could not find a job description on that page. {PASTE_INSTEAD}")
    return page, reader
