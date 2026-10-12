"""The rules behind the inbox: what a mail is, which application it belongs
to, and what a run of rejections has in common. All pure functions.
"""

from dataclasses import dataclass

import pytest

from backend.modules.inbox.classifier import classify
from backend.modules.inbox.insights import Outcome, find_patterns
from backend.modules.inbox.linking import find_application, next_status, same_company

INTEREST = "Thank you for your interest."


@pytest.mark.parametrize(
    ("subject", "sender", "address", "body", "expected"),
    [
        (
            "Thank you for applying to Razorpay",
            "Razorpay Careers",
            "no-reply@razorpay.com",
            "We received your application for the Software Development Engineer role. "
            "If shortlisted you may be invited to an interview.",
            ("applied", "Razorpay", "Software Development Engineer"),
        ),
        (
            "Gaurav, your application was sent to Terminal 2",
            "LinkedIn",
            "jobs-noreply@linkedin.com",
            "Your application was sent to Terminal 2.",
            ("applied", "Terminal 2", None),
        ),
        (
            "Update on your application for React Native Developer at Acme Corp",
            "Acme Corp Recruiting",
            "recruiting@acme.com",
            f"{INTEREST} Unfortunately, we have decided to move forward with other candidates.",
            ("rejected", "Acme", "React Native Developer"),
        ),
        (
            "Application received for React Native Internship at Humanity Founders",
            "Internshala",
            "student@internshala.com",
            "Your application has been submitted.",
            ("applied", "Humanity Founders", "React Native Internship"),
        ),
        (
            "Interview invitation - Frontend Engineer",
            "Priya from Swiggy",
            "priya@swiggy.in",
            "We would like to schedule an interview with you next week.",
            ("interview", "Swiggy", "Frontend Engineer"),
        ),
        (
            "Your HackerRank assessment for Zomato",
            "Zomato Hiring Team",
            "hiring@zomato.com",
            "Please complete the coding test within 3 days.",
            ("assessment", "Zomato", None),
        ),
        (
            "Offer letter - Software Engineer",
            "CRED People Team",
            "people@cred.club",
            "We are pleased to offer you the position of Software Engineer.",
            ("offer", "CRED", "Software Engineer"),
        ),
        (
            "Thank you for your application",
            "Workday",
            "acme@myworkday.com",
            "Thank you for applying for the position of Mobile Engineer II at Acme Pvt Ltd.",
            ("applied", "Acme", "Mobile Engineer II"),
        ),
        (
            "Regarding your candidature",
            "TCS Talent Acquisition",
            "ta@tcs.com",
            "We regret to inform you that you have not been shortlisted for the role of "
            "Systems Engineer.",
            ("rejected", "TCS", "Systems Engineer"),
        ),
        (
            "Next steps",
            "Greenhouse",
            "no-reply@greenhouse.io",
            "Hello, please see the attached document about the position.",
            ("unclear", None, None),
        ),
    ],
)
def test_says_what_a_job_mail_is(
    subject: str,
    sender: str,
    address: str,
    body: str,
    expected: tuple[str, str | None, str | None],
) -> None:
    found = classify(subject, sender, address, body)
    assert found is not None
    assert (found.kind, found.company, found.role) == expected


# Subjects taken from a real inbox, where the first version of the rules got them wrong.
def test_lessons_from_a_real_inbox() -> None:
    def kind_of(subject: str, sender: str, address: str, body: str = "") -> str | None:
        found = classify(subject, sender, address, body)
        return found.kind if found else None

    # A reminder to finish applying is not an application.
    reminder = "Complete your application: Full Stack Engineer - AI Trainer"
    assert kind_of(reminder, "Indeed Apply", "indeedapply@indeed.com") is None
    assert kind_of("Get your application ready", "ChatGPT", "noreply@openai.com") is None
    # A contest on a job site is not an assessment.
    assert kind_of("Young turks: 3 hrs to R1", "Naukri Campus", "c@naukri.com", "Test") is None

    # An acknowledgement that mentions offers is not an offer.
    thanks = classify(
        "It’s great that you’re interested in Accenture!",
        "Accenture",
        "noreply@accenture.com",
        "Thank you for applying for Application Developer. If selected, you may receive a job "
        "offer after the interviews.",
    )
    assert thanks is not None and thanks.kind == "applied"

    # The job board is never the company; the role comes from the subject.
    indeed = classify(
        "Indeed Application: Frontend Engineer",
        "Indeed Apply",
        "indeedapply@indeed.com",
        "Your application has been submitted to Quince.",
    )
    assert indeed is not None
    assert (indeed.kind, indeed.company, indeed.role) == ("applied", "Quince", "Frontend Engineer")

    # In a reply thread the sender is a person: use where they work, or ask.
    reply = classify(
        "Re: EliteEvince - Careers - React Native Developers intern",
        "Devang Soni",
        "devang@eliteevince.com",
        "Thank you for applying. Please share your availability.",
    )
    assert reply is not None and reply.company == "Eliteevince"
    personal = classify(
        "Re: Your application", "Asha Rao", "asha.rao@gmail.com", "Thanks for applying."
    )
    assert personal is not None and personal.company is None

    assert (
        kind_of("Screening Round Invitation: Coorix Internship Program", "Coorix", "hr@coorix.com")
        == "interview"
    )


def test_a_second_role_at_the_same_company_is_a_second_application() -> None:
    first = App("Accenture", "Application Developer")
    again = find_application([first], "Accenture", "Web Design Associate", new_application=True)
    assert again == "none"
    # News about the one application still finds it, whatever the mail calls the role.
    assert find_application([first], "Accenture", "Web Design Associate") is first
    same = find_application([first], "Accenture", "Application Developer", new_application=True)
    assert same is first
    unnamed = App("Quince", "Role not stated")
    found = find_application(
        [unnamed], "Quince", "SDE", new_application=True, unnamed_role="Role not stated"
    )
    assert found is unnamed


@pytest.mark.parametrize(
    ("subject", "sender", "address", "body"),
    [
        (
            "15 new jobs for React Native Developer",
            "LinkedIn Job Alerts",
            "a@linkedin.com",
            "Apply",
        ),
        ("Your order has shipped", "Amazon", "ship@amazon.in", "Unfortunately item 2 is late."),
        ("Your profile was viewed by 3 recruiters", "Naukri", "info@naukri.com", "See who."),
        ("Acme is hiring: Senior Engineer", "Wellfound", "t@wellfound.com", "A job for you."),
        ("Lunch on Friday?", "Rahul", "rahul@gmail.com", "Are you free?"),
    ],
)
def test_mail_that_is_not_about_your_application_is_not_kept(
    subject: str, sender: str, address: str, body: str
) -> None:
    assert classify(subject, sender, address, body) is None


@dataclass
class App:
    company: str
    role: str
    status: str = "applied"


def test_company_names_match_however_they_are_written() -> None:
    assert same_company("Acme Technologies Pvt. Ltd.", "ACME")
    assert same_company("Razorpay", "Razorpay Software")
    assert not same_company("Go", "Google")
    assert not same_company("Acme", "Apex")


def test_a_mail_finds_its_application_or_asks() -> None:
    mobile, web = App("Acme", "React Native Developer"), App("Acme", "Frontend Engineer")
    other = App("Swiggy", "Backend Engineer")

    assert find_application([other], "Swiggy Careers", None) is other
    assert find_application([other], "Zomato", "Backend Engineer") == "none"
    # Two applications at one company: the role settles it, or the user does.
    assert find_application([mobile, web, other], "Acme", "React Native Developer") is mobile
    assert find_application([mobile, web], "Acme", None) == "ambiguous"
    assert find_application([mobile, web], "Acme", "Data Analyst") == "ambiguous"
    assert find_application([mobile], None, "React Native Developer") == "ambiguous"


def test_a_status_only_moves_forward() -> None:
    assert next_status("saved", "applied") == "applied"
    assert next_status("applied", "assessment") == "replied"
    assert next_status("applied", "interview") == "interview"
    assert next_status("interview", "applied") is None  # a late "received" mail
    assert next_status("interview", "rejected") == "rejected"
    assert next_status("offer", "rejected") is None
    assert next_status("rejected", "applied") is None
    assert next_status("rejected", "interview") == "interview"  # they came back
    assert next_status("applied", "unclear") is None


def test_rejections_are_explained_by_what_the_jobs_asked_for() -> None:
    outcomes = [
        Outcome("rejected", 40, "well_short", 5, ("Kubernetes", "Go"), checked=True),
        Outcome("rejected", 45, "well_short", 3, ("Kubernetes",), checked=True),
        Outcome("rejected", 72, "meets", 1, ("Kubernetes", "GraphQL"), checked=True),
        Outcome("rejected"),  # tracked from a mail, never checked
        Outcome("interview", 81, "meets", 1, (), checked=True),
        Outcome("applied", 60, checked=True),
    ]
    findings = {item.title: item.detail for item in find_patterns(outcomes)}

    assert "2 of your 3 checked rejections" in findings["Experience is the main reason"]
    assert "Kubernetes (3 times)" in findings["Skills that keep coming up missing"]
    assert "2 of your 3" in findings["Many of these were long shots"]
    assert "scored 81 on average" in findings["What your interviews had in common"]
    assert "1 of your 4 rejections" in findings["Some rejections cannot be explained yet"]


def test_no_rejections_means_nothing_to_say() -> None:
    assert find_patterns([Outcome("applied"), Outcome("interview", 80, checked=True)]) == []
