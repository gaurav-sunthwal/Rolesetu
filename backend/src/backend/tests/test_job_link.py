"""Reading a job from its link: the page reader and the fetcher's safety checks."""

import json

import httpx
import pytest
from httpx import AsyncClient, Response
from pydantic import ValidationError

from backend.core.config import get_settings
from backend.modules.matches import service as matches_service
from backend.modules.matches.fetching import reader, rendered_fetch
from backend.modules.matches.fetching.job_page import html_to_text, is_job_list, read_job_page
from backend.modules.matches.fetching.safe_fetch import (
    PageBlockedError,
    PageFetchError,
    assert_public,
)
from backend.modules.matches.schemas import MatchCreate

DESCRIPTION = (
    "<p>About the job:</p>Key Responsibilities:<br />\n"
    "1. Build web interfaces using HTML, CSS, JavaScript, and React.<br />\n"
    "2. Develop backend services using Python, Node.js or Flask.<br />\n"
    "3. Work with MySQL and MongoDB to manage databases.<br><br>"
    "<p>About Company:</p>We provide application solutions to clients across many industries."
)
POSTING = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Full Stack AI Developer - Fresher (WFH)",
    "description": DESCRIPTION,
    "employmentType": "FULL_TIME",
    "jobLocation": [
        {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "IN",
                "addressLocality": "Hyderabad",
                "addressRegion": "Telangana",
            },
        }
    ],
    "hiringOrganization": {"@type": "Organization", "name": "Megaminds IT Services"},
    "datePosted": "2026-10-09",
    "jobLocationType": "TELECOMMUTE",
    "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "INR",
        "value": {"minValue": 200000, "maxValue": 240000, "unitText": "YEAR"},
    },
    "skills": "MySQL, HTML, Docker, Amazon Web Services (AWS)",
}


def page_with(*blocks: object) -> str:
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(block)}</script>' for block in blocks
    )
    return (
        f"<html><head><title>Job | Site</title>{scripts}</head><body><nav>Menu</nav></body></html>"
    )


def test_reads_the_structured_job_block() -> None:
    breadcrumbs = {"@type": "BreadcrumbList", "itemListElement": []}
    page = read_job_page(page_with([POSTING, breadcrumbs]))
    assert page is not None and page.source == "structured"
    assert page.title == "Full Stack AI Developer - Fresher (WFH)"
    assert page.company == "Megaminds IT Services"
    assert page.location == "Remote (Hyderabad, Telangana, IN)"
    assert page.employment_type == "Full time"
    assert page.salary == "INR 200,000 to 240,000 per year"
    assert page.posted_on == "2026-10-09"
    assert page.description.splitlines()[:2] == ["About the job:", "Key Responsibilities:"]


def test_listed_skills_missing_from_the_description_are_added_for_scoring() -> None:
    page = read_job_page(page_with(POSTING))
    assert page is not None
    # MySQL and HTML are already in the description; Docker and AWS are not.
    assert page.as_text().endswith("Skills required: Docker, Amazon Web Services (AWS)")


def test_whole_salaries_are_shown_without_decimals() -> None:
    pay = {"currency": "USD", "value": {"minValue": 230000.0, "maxValue": 260000.0}}
    page = read_job_page(page_with(POSTING | {"baseSalary": pay}))
    assert page is not None and page.salary == "USD 230,000 to 260,000"


def test_placeholder_location_and_salary_are_left_out() -> None:
    posting = POSTING | {
        "jobLocationType": None,
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "-"}},
        "baseSalary": {"currency": "INR", "value": {"value": "Not disclosed", "unitText": "P.A."}},
    }
    page = read_job_page(page_with(posting))
    assert page is not None and page.location is None and page.salary is None


def test_finds_a_job_nested_in_a_graph() -> None:
    page = read_job_page(page_with({"@context": "https://schema.org", "@graph": [POSTING]}))
    assert page is not None and page.company == "Megaminds IT Services"


def test_broken_json_block_is_skipped_not_fatal() -> None:
    markup = '<script type="application/ld+json">{not json</script>' + page_with(POSTING)
    assert read_job_page(markup) is not None


def test_falls_back_to_page_text_without_a_structured_block() -> None:
    body = "<h2>Requirements</h2>" + "<p>React and TypeScript developer who knows Docker.</p>" * 12
    markup = (
        "<html><head><title>Frontend Engineer - Acme</title></head><body>"
        f"<nav>Home Jobs Login</nav><main>{body}</main><footer>Copyright</footer>"
        "<script>track()</script></body></html>"
    )
    page = read_job_page(markup)
    assert page is not None and page.source == "page text"
    assert page.title == "Frontend Engineer"
    assert "Home Jobs Login" not in page.description and "track()" not in page.description


def test_a_page_with_no_job_gives_nothing() -> None:
    assert read_job_page("<html><body><p>Please sign in to continue.</p></body></html>") is None


def test_html_becomes_one_line_per_block() -> None:
    assert html_to_text("<p>One</p><ul><li>Two &amp; three</li><li>Four</li></ul>") == (
        "One\nTwo & three\nFour"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1:80/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "ftp://example.com/file",
        "https://user:secret@example.com/",
        "https://example.com:8443/",
        "not a link",
    ],
)
async def test_unsafe_links_are_refused_before_any_request(url: str) -> None:
    with pytest.raises(PageFetchError):
        await assert_public(url)


def test_a_check_needs_a_link_or_a_description() -> None:
    assert MatchCreate(url="https://example.com/job/1").jd_text is None
    with pytest.raises(ValidationError):
        MatchCreate()
    with pytest.raises(ValidationError):
        MatchCreate(jd_text="too short")


def test_a_search_page_is_recognised_as_a_list_and_not_read_as_a_job() -> None:
    cards = "<div><h3>Android Developer</h3><p>Requirements: Kotlin. Apply now</p></div>" * 30
    markup = (
        "<html><head><title>34 Work From Home Jobs in Oct 2026 | Site</title></head>"
        f"<body><main>{cards}</main></body></html>"
    )
    assert is_job_list(markup)
    assert read_job_page(markup) is None


def test_a_page_marked_up_as_a_list_is_recognised() -> None:
    assert is_job_list(page_with({"@type": "ItemList", "itemListElement": []}))
    assert not is_job_list(page_with(POSTING))


# Falling back to the paid page reader -------------------------------------------------

MATCHES = "/api/v1/matches"
JOB_URL = "https://jobs.example.com/frontend-engineer"
PROFILE = {
    "full_name": "Asha Rao",
    "skills": [{"id": "s1", "name": "React", "level": "intermediate"}],
}
BLOCKED = PageBlockedError("This site does not let us read the page. Paste it instead.")


class FakeReaders:
    """Stands in for both fetchers and counts how often each was used."""

    def __init__(self, direct: str | PageFetchError, rendered: str | None) -> None:
        self.direct, self.rendered = direct, rendered
        self.direct_calls = self.rendered_calls = 0

    async def fetch_page(self, url: str) -> tuple[str, str]:
        self.direct_calls += 1
        if isinstance(self.direct, PageFetchError):
            raise self.direct
        return url, self.direct

    async def fetch_rendered(self, url: str) -> str | None:
        self.rendered_calls += 1
        return self.rendered


def use_readers(
    monkeypatch: pytest.MonkeyPatch,
    direct: str | PageFetchError,
    rendered: str | None = None,
    *,
    keys: list[str] | None = None,
) -> FakeReaders:
    readers = FakeReaders(direct, rendered)
    monkeypatch.setattr(reader, "fetch_page", readers.fetch_page)
    monkeypatch.setattr(reader, "fetch_rendered", readers.fetch_rendered)
    monkeypatch.setattr(get_settings(), "match_engine", "local")
    monkeypatch.setattr(get_settings(), "context_api_keys", ["key-1"] if keys is None else keys)
    return readers


async def check_link(client: AsyncClient, url: str = JOB_URL) -> Response:
    await client.put("/api/v1/profile/me", json=PROFILE)
    return await client.post(MATCHES, json={"url": url})


async def test_a_page_we_can_read_ourselves_never_uses_the_paid_reader(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = use_readers(monkeypatch, page_with(POSTING), page_with(POSTING))
    response = await check_link(client)
    assert response.is_success and response.json()["company"] == "Megaminds IT Services"
    assert (readers.direct_calls, readers.rendered_calls) == (1, 0)


async def test_a_blocked_page_is_read_through_the_paid_reader(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = use_readers(monkeypatch, BLOCKED, page_with(POSTING))
    response = await check_link(client)
    assert response.is_success and response.json()["company"] == "Megaminds IT Services"
    assert readers.rendered_calls == 1


async def test_a_page_with_no_job_in_its_html_is_read_through_the_paid_reader(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    shell = "<html><body><div id='root'></div><script src='app.js'></script></body></html>"
    readers = use_readers(monkeypatch, shell, page_with(POSTING))
    assert (await check_link(client)).is_success
    assert readers.rendered_calls == 1


async def test_the_sites_own_error_is_shown_when_the_paid_reader_also_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_readers(monkeypatch, BLOCKED, None)
    response = await check_link(client)
    assert response.status_code == 422
    assert "does not let us read the page" in response.json()["detail"]


@pytest.mark.parametrize(
    "direct",
    [
        PageFetchError("That job page no longer exists."),
        "<html><head><title>34 Jobs in Pune | Site</title></head><body></body></html>",
    ],
    ids=["removed listing", "list of jobs"],
)
async def test_no_credit_is_spent_on_a_link_that_cannot_be_a_job(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, direct: str | PageFetchError
) -> None:
    readers = use_readers(monkeypatch, direct, page_with(POSTING))
    assert (await check_link(client)).status_code == 422
    assert readers.rendered_calls == 0


async def test_without_a_key_the_paid_reader_is_off(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = use_readers(monkeypatch, BLOCKED, page_with(POSTING), keys=[])
    assert (await check_link(client)).status_code == 422
    assert readers.rendered_calls == 0


async def test_paid_reads_stop_at_the_daily_allowance(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(matches_service, "MAX_RENDERED_READS_PER_DAY", 1)
    readers = use_readers(monkeypatch, BLOCKED, page_with(POSTING))
    assert (await check_link(client)).is_success
    # A second, different link: the allowance is used, so no second paid call.
    assert (await check_link(client, f"{JOB_URL}-2")).status_code == 422
    assert readers.rendered_calls == 1


def use_context_api(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=handler, **kw))
    monkeypatch.setattr(get_settings(), "context_api_keys", ["spent", "good"])


async def test_the_next_key_is_used_when_one_has_run_out(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        if request.headers["authorization"] == "Bearer spent":
            return httpx.Response(401, json={"error": "USAGE_EXCEEDED"})
        assert json.loads(request.content)["url"] == JOB_URL
        return httpx.Response(200, json={"html": {"success": True, "data": "<p>Job</p>"}})

    use_context_api(monkeypatch, httpx.MockTransport(answer))
    assert await rendered_fetch.fetch_rendered(JOB_URL) == "<p>Job</p>"
    assert seen == ["Bearer spent", "Bearer good"]


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(200, json={"html": {"success": False, "error_code": "WEBSITE_BLOCKED"}}),
        httpx.Response(200, text="not json"),
        httpx.Response(408),
        httpx.Response(401),
    ],
    ids=["site blocked it too", "unexpected body", "timed out", "every key refused"],
)
async def test_a_failed_paid_read_gives_nothing_instead_of_an_error(
    monkeypatch: pytest.MonkeyPatch, reply: httpx.Response
) -> None:
    use_context_api(monkeypatch, httpx.MockTransport(lambda request: reply))
    assert await rendered_fetch.fetch_rendered(JOB_URL) is None
