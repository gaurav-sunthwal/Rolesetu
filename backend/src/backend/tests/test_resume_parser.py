"""The local resume parser, checked against six differently laid-out PDFs
(see tests/fixtures/resumes) and against the individual rules.
"""

from pathlib import Path

import pytest

from backend.modules.profiles.schemas import ProfileWrite
from backend.modules.resumes.extraction import dates
from backend.modules.resumes.extraction.experience import parse_experience
from backend.modules.resumes.extraction.lines import Line
from backend.modules.resumes.extraction.parser import NoTextInPdfError, parse_lines, parse_pdf
from backend.modules.resumes.extraction.projects import parse_projects
from backend.modules.resumes.extraction.sections import heading_of
from backend.modules.resumes.extraction.skills import parse_skills
from backend.modules.resumes.merge import apply_resume
from backend.modules.resumes.normalize import to_profile

FIXTURES = Path(__file__).parent / "fixtures" / "resumes"


def load(name: str) -> ProfileWrite:
    return to_profile(parse_pdf((FIXTURES / f"{name}.pdf").read_bytes()))


def skill_names(profile: ProfileWrite) -> list[str]:
    return [skill.name for skill in profile.skills]


# --- whole resumes -----------------------------------------------------------


def test_classic_single_column() -> None:
    profile = load("classic")
    assert profile.full_name == "Asha Rao"
    assert profile.headline == "Frontend Engineer"
    assert profile.location == "Bengaluru, India"
    assert profile.phone == "+91 98765 43210"
    assert profile.links.linkedin == "https://www.linkedin.com/in/asharao"
    assert profile.links.github == "https://github.com/asharao"
    assert profile.links.portfolio == "https://asharao.dev"
    assert skill_names(profile)[:4] == ["JavaScript", "TypeScript", "Python", "SQL"]
    assert "GitHub Actions" in skill_names(profile) and len(profile.skills) == 14

    current, intern = profile.experience
    assert (current.title, current.company) == (
        "Frontend Developer",
        "Phenko Technologies Pvt. Ltd.",
    )
    assert (current.start, current.end, current.location) == ("2023-06", None, "Bengaluru, India")
    # A bullet that wrapped onto a second line is put back together.
    assert current.description.splitlines()[1].endswith("over two releases.")
    assert len(current.description.splitlines()) == 3
    assert (intern.title, intern.company, intern.start, intern.end) == (
        "Software Engineering Intern",
        "Globex Labs",
        "2023-01",
        "2023-05",
    )

    video, tracker = profile.projects
    assert video.name == "Realtime Video App"
    assert video.tech == ["WebRTC", "Node.js", "Socket.IO"]
    assert video.url == "https://github.com/asharao/video-app"
    assert tracker.tech == ["Next.js", "PostgreSQL", "Tailwind CSS"]

    (school,) = profile.education
    assert school.school == "Visvesvaraya Technological University"
    assert (school.degree, school.field) == ("Bachelor of Engineering", "Computer Science")
    assert (school.start_year, school.end_year) == (2019, 2023)


def test_two_column_sidebar_is_read_one_column_at_a_time() -> None:
    profile = load("twocol")
    assert profile.full_name == "Rahul Verma"  # written in capitals in the file
    assert profile.location == "Pune, Maharashtra"
    assert profile.links.github == "https://github.com/rverma"
    assert skill_names(profile) == [
        "Python", "Django", "FastAPI", "PostgreSQL", "Redis", "AWS", "Docker", "Kubernetes",
    ]  # fmt: skip
    # A level is taken only where the resume states one.
    levels = {skill.name: skill.level for skill in profile.skills}
    assert levels["Python"] == "advanced" and levels["AWS"] == "beginner"
    assert levels["Django"] is None

    first, second = profile.experience
    assert (first.title, first.company) == ("Senior Systems Engineer", "Infosys Limited")
    assert (first.start, first.end) == ("2021-07", "2024-03")
    assert "banking client." in first.description
    assert second.company == "Tata Consultancy Services"
    assert profile.projects[0].tech == ["FastAPI", "Redis", "Docker"]
    assert profile.education[0].field == "Information Technology"


def test_latex_style_with_small_caps_and_company_first() -> None:
    profile = load("jake")
    assert profile.full_name == "Karan Mehta"
    assert profile.location is None  # the resume does not give one
    assert [(r.title, r.company) for r in profile.experience] == [
        ("Software Development Engineer II", "Razorpay"),
        ("Software Engineering Intern", "Microsoft"),
    ]
    assert profile.experience[0].location == "Bengaluru, India"
    assert len(profile.experience[0].description.splitlines()) == 3
    assert [p.name for p in profile.projects] == ["Gitlytics", "Simple Paintball"]
    assert profile.projects[0].tech == ["Python", "Flask", "React", "PostgreSQL", "Docker"]
    assert "C/C++" in skill_names(profile) and "VS Code" in skill_names(profile)
    college, school = profile.education
    assert college.field == "Computer Science and Engineering"
    assert (school.school, school.degree, school.field) == (
        "Delhi Public School",
        "Class XII",
        None,
    )


def test_resume_with_no_bold_text() -> None:
    profile = load("plain")
    assert [(r.title, r.company, r.start, r.end) for r in profile.experience] == [
        ("Product Designer", "Zomato", "2021-01", None),
        ("UX Design Intern", "Swiggy", "2020-06", "2020-12"),
    ]
    assert [p.name for p in profile.projects] == ["Travel Buddy", "Portfolio Website"]
    assert profile.projects[0].tech == ["Figma", "Maze"]
    assert profile.education[0].school == "National Institute of Design, Ahmedabad"


def test_prose_descriptions_and_inline_dates() -> None:
    profile = load("compact")
    assert profile.links.portfolio == "https://meeranair.io"
    assert profile.phone == "(415) 555-0132"
    assert (profile.experience[0].title, profile.experience[0].company) == (
        "Data Analyst",
        "Northwind Traders",
    )
    assert profile.experience[0].description.startswith("Own weekly revenue reporting")
    assert [(e.school, e.degree, e.field) for e in profile.education] == [
        ("University of California, Berkeley", "Master of Science", "Statistics"),
        ("University of Mumbai", "B.Sc.", "Mathematics"),
    ]


def test_undated_role_headings_with_colons_and_a_second_page() -> None:
    profile = load("tricky")
    assert profile.full_name == "Dr. Arjun K. Nambiar"
    assert profile.headline == "Machine Learning Engineer"
    titles = [role.title for role in profile.experience]
    assert titles == ["Senior ML Engineer", "Decision Scientist", "Freelance Data Scientist"]
    freelance = profile.experience[-1]
    assert freelance.start is None  # no date in the resume, so none is invented
    assert freelance.description.startswith("Delivered churn models")
    # Education sits on page two.
    assert [e.degree for e in profile.education] == ["Ph.D.", "M.Tech"]
    assert profile.projects[0].url == "https://github.com/arjunkn/papertrail"


def test_pdf_without_text_is_reported_as_a_scan() -> None:
    blank = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF"
    )
    with pytest.raises(NoTextInPdfError):
        parse_pdf(blank)


# --- individual rules --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "start", "end", "current"),
    [
        ("Jun 2023 – Present", "2023-06", None, True),
        ("June 2021 - Aug. 2022", "2021-06", "2022-08", False),
        ("07/2021 – 03/2024", "2021-07", "2024-03", False),
        ("2018 to 2021", "2018-01", "2021-01", False),
        ("Sept '19 — till date", "2019-09", None, True),
        ("March 2022 to Present", "2022-03", None, True),
    ],
)
def test_date_ranges(text: str, start: str, end: str | None, current: bool) -> None:
    found = dates.find_range(text)
    assert found is not None
    assert (found.start, found.end, found.is_current) == (start, end, current)


@pytest.mark.parametrize("text", ["PostgreSQL 14", "handled 2 million requests", "version 3.11"])
def test_numbers_that_are_not_dates(text: str) -> None:
    assert dates.find_dates(text) is None


def test_headings_are_recognised_but_labelled_content_is_not() -> None:
    assert heading_of(Line("WORK EXPERIENCE")) == "experience"
    assert heading_of(Line("Skills & Tools")) == "skills"
    assert heading_of(Line("Academic Qualifications:")) == "education"
    assert heading_of(Line("Languages: Python, Go")) is None
    assert heading_of(Line("Led the experience team for two years")) is None


def test_skills_are_split_and_sentences_are_dropped() -> None:
    skills = parse_skills(
        [
            Line("Languages: Python, Go; SQL (Postgres)"),
            Line("• CI/CD | Docker • Kubernetes (Expert)"),
            Line("I enjoy working with distributed systems and learning new things every day"),
        ]
    )
    assert [skill.name for skill in skills] == [
        "Python", "Go", "SQL (Postgres)", "CI/CD", "Docker", "Kubernetes",
    ]  # fmt: skip
    assert skills[-1].level == "advanced"


def test_resume_without_recognisable_sections_yields_nothing() -> None:
    profile = to_profile(parse_lines([Line("Hello"), Line("This is just a letter, not a resume.")]))
    assert not (profile.skills or profile.experience or profile.projects or profile.education)


# --- layouts first seen in a real resume ---------------------------------------


def test_detail_line_under_a_title_gives_the_location_and_is_kept() -> None:
    (role,) = parse_experience(
        [
            Line("Mobile Developer Intern \u2014 Terminal 2\t09/2025 \u2013 Present", bold=True),
            Line("ShopApp (short-video commerce app) | Pune, India | Google Play \u00b7 App Store"),
            Line("\u2022 Built a production React Native app with vertical video feeds, used"),
            Line("by 2,000+ users on Android and iOS."),
            Line("\u2022 Integrated Razorpay and Stripe payments."),
        ]
    )
    assert (role.title, role.company) == ("Mobile Developer Intern", "Terminal 2")
    assert (role.location, role.start, role.is_current) == ("Pune, India", "2025-09", True)
    assert role.description is not None
    first, second, third = role.description.splitlines()
    assert first == "ShopApp (short-video commerce app) | Google Play | App Store"
    assert second.endswith("used by 2,000+ users on Android and iOS.")  # wrapped bullet rejoined
    assert third == "Integrated Razorpay and Stripe payments."


def test_project_tagline_is_not_tech_and_the_pipe_line_is() -> None:
    (project,) = parse_projects(
        [
            Line(
                "Swipe Mart \u2014 Location-Based Marketplace\tLive Demo \u00b7 GitHub", bold=True
            ),
            Line("Expo | Next.js | TypeScript | PostgreSQL + PostGIS"),
            Line("\u2022 Swipe app for selling unused items to nearby people."),
        ]
    )
    assert project.name == "Swipe Mart"
    assert project.tech == ["Expo", "Next.js", "TypeScript", "PostgreSQL + PostGIS"]
    assert project.description == (
        "Location-Based Marketplace\nSwipe app for selling unused items to nearby people."
    )


def test_skills_wrapped_across_lines_and_commas_inside_brackets() -> None:
    skills = parse_skills(
        [
            Line("Mobile: React Native, Expo, Push Notifications (Expo Notifications,"),
            Line("FCM), Android, iOS"),
            Line("Languages: JavaScript (ES6+), TypeScript"),
            Line("Tools: Git, GitHub,"),
            Line("Sentry"),
        ]
    )
    assert [skill.name for skill in skills] == [
        "React Native", "Expo", "Push Notifications (Expo Notifications, FCM)", "Android", "iOS",
        "JavaScript (ES6+)", "TypeScript", "Git", "GitHub", "Sentry",
    ]  # fmt: skip


def test_headline_in_capitals_is_softened_but_acronyms_are_kept() -> None:
    resume = parse_lines(
        [
            Line("JANE DOE", size=20, bold=True),
            Line("REACT NATIVE DEVELOPER | ANDROID & iOS", bold=True),
            Line("Skills"),
            Line("AWS, Go"),
        ]
    )
    assert resume.full_name == "Jane Doe"
    assert resume.headline == "React Native Developer | Android & iOS"


# --- merging into an existing profile ----------------------------------------


def test_merge_keeps_what_is_there_and_adds_what_is_new() -> None:
    parsed = load("classic")
    current = ProfileWrite.model_validate(
        {
            "full_name": "Asha R.",
            "skills": [{"id": "mine", "name": "react", "level": "advanced"}],
            "experience": [
                {
                    "id": "e1",
                    "title": "frontend developer",
                    "company": "Phenko Technologies Pvt. Ltd.",
                    "start": "2023-06",
                    "description": "My own wording.",
                }
            ],
        }
    )
    merged = apply_resume(current, parsed, "merge")

    assert merged.full_name == "Asha R."  # never overwritten
    assert merged.headline == "Frontend Engineer"  # blank, so filled in
    react = [skill for skill in merged.skills if skill.name.lower() == "react"]
    assert len(react) == 1 and react[0].id == "mine" and react[0].level == "advanced"
    assert len(merged.skills) == 14
    assert len(merged.experience) == 2  # the matching role is not duplicated
    assert merged.experience[0].description == "My own wording."
    assert merged.experience[1].company == "Globex Labs"


def test_replace_takes_the_resume_as_the_whole_profile() -> None:
    parsed = load("classic")
    current = ProfileWrite.model_validate({"full_name": "Someone Else", "headline": "Old"})
    replaced = apply_resume(current, parsed, "replace")
    assert replaced.full_name == "Asha Rao" and replaced.headline == "Frontend Engineer"
