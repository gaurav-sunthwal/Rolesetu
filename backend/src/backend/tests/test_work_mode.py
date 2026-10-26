import pytest

from backend.modules.career_jobs.work_mode import WorkMode, work_mode_of


@pytest.mark.parametrize(
    ("location", "title", "description", "expected"),
    [
        # Said in the location or tagged on the title.
        ("Remote - India - Remote", "Engineer", "", "remote"),
        ("Bengaluru; Remote - Remote", "Engineer", "", "remote"),
        ("Pune (Hybrid)", "Engineer", "", "hybrid"),
        ("Pune", "Data Analyst (Remote)", "", "remote"),
        ("Pune", "Support Engineer - WFO", "", "onsite"),
        # Phrases in the description, as real postings word them.
        ("Pune", "Engineer", "India Consulting Hybrid Professional Bangalore, IN", "hybrid"),
        ("Pune", "Engineer", "We want to hear from you. #LI-Hybrid", "hybrid"),
        ("Pune", "Engineer", "This role will be eligible for our hybrid work model.", "hybrid"),
        ("Pune", "Engineer", "Required to be in the Hyderabad office three days a week.", "hybrid"),
        ("Pune", "Engineer", "Work Mode: Hybrid", "hybrid"),
        ("Pune", "Engineer", "Shift Timings- 5pm IST ( Remote opportunity)", "remote"),
        ("Pune", "Engineer", "Thrive in a remote-first, fast-moving team.", "remote"),
        ("Pune", "Engineer", "Job Location: Chennai/Pune (Work from office)", "onsite"),
        ("Pune", "Engineer", "This role will require an on-site presence.", "onsite"),
        ("Pune", "Engineer", "This is a client onsite project.", "onsite"),
        ("Pune", "Engineer", "Please note this is not a remote role.", "onsite"),
        ("Pune", "Engineer", "Work arrangement: Work from office", "onsite"),
    ],
)
def test_reads_the_work_mode(location: str, title: str, description: str, expected: str) -> None:
    assert work_mode_of(title=title, location=location, description=description) == expected


@pytest.mark.parametrize(
    ("title", "description"),
    [
        # About the work, not where it is done.
        ("Hybrid Cloud Architect", "Shape their hybrid cloud and AI journeys."),
        ("Remote Sensing Scientist", "Provide remote support and remote maintenance."),
        ("Engineer", "Coordinate with global onsite-offshore delivery teams."),
        ("Engineer", "Build hybrid semantic search for retrieval."),
        # Perks and option lists, not this job's arrangement.
        ("Engineer", "Work from anywhere for up to 8 weeks per year."),
        ("Engineer", "Be it remote work, or flexible work hours, you will thrive."),
        ("Engineer", "Roles range from in-office, to office-flex, to fully remote."),
        ("Engineer", "Work with remote or multi-site teams."),
    ],
)
def test_says_not_stated_rather_than_guessing(title: str, description: str) -> None:
    mode: WorkMode = work_mode_of(title=title, location="Bengaluru", description=description)
    assert mode == "not_stated"
