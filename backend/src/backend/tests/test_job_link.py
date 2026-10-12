"""Reading a job from its link: the page reader and the fetcher's safety checks."""

import json

import pytest
from pydantic import ValidationError

from backend.modules.matches.fetching.job_page import html_to_text, is_job_list, read_job_page
from backend.modules.matches.fetching.safe_fetch import PageFetchError, _assert_public
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
        await _assert_public(url)


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
