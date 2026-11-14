"""Labelled cases for reusing saved answers (see `questions.py`).

`SAVED` is one realistic answer bank: the questions a job seeker has answered
before, stored under the keys the extension makes for them. `ASKED` is a new
form's questions, worded differently, each with the saved keys that would be a
right answer. An empty set means no saved answer fits, and filling one in would
be a mistake: those cases are the ones that keep the matcher honest.
"""

import re


def key_for(question: str) -> str:
    """The key the extension stores a question under (`questionKey` in fields.ts)."""
    words = re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")
    return f"q_{words[:56].rstrip('_')}"


SAVED_QUESTIONS = [
    "Do you have a laptop with a stable internet connection?",
    "Are you available for a 6 month full-time internship?",
    "Are you comfortable working in night shifts?",
    "Have you worked on any project using React?",
    "Have you worked with Python before?",
    "Why should we hire you for this role?",
    "Tell us about yourself",
    "Describe a challenging project you have worked on",
    "Are you willing to work from office 5 days a week?",
    "Do you have a valid driving license?",
    "Are you comfortable signing a 2 year service agreement?",
    "Can you start immediately?",
    "Total years of experience in Java",
    "What are your strengths?",
    "Rate your English communication skills",
]

KNOWN_KEYS = [
    "notice_period",
    "expected_ctc",
    "current_ctc",
    "relocation",
    "work_authorization",
    "heard_from",
    "why_this_role",
]

SAVED: dict[str, str] = {
    **{key: f"(answer to {key})" for key in KNOWN_KEYS},
    **{key_for(question): f"(answer to {question})" for question in SAVED_QUESTIONS},
}

LAPTOP = key_for("Do you have a laptop with a stable internet connection?")
INTERNSHIP = key_for("Are you available for a 6 month full-time internship?")
NIGHT_SHIFTS = key_for("Are you comfortable working in night shifts?")
REACT = key_for("Have you worked on any project using React?")
WHY_HIRE = key_for("Why should we hire you for this role?")
ABOUT_YOU = key_for("Tell us about yourself")
HARD_PROJECT = key_for("Describe a challenging project you have worked on")
OFFICE = key_for("Are you willing to work from office 5 days a week?")
LICENSE = key_for("Do you have a valid driving license?")
BOND = key_for("Are you comfortable signing a 2 year service agreement?")
START_NOW = key_for("Can you start immediately?")
JAVA_YEARS = key_for("Total years of experience in Java")
STRENGTHS = key_for("What are your strengths?")
ENGLISH = key_for("Rate your English communication skills")

NONE: frozenset[str] = frozenset()

ASKED: list[tuple[str, frozenset[str]]] = [
    # Same question, other words.
    ("How soon can you join us?", frozenset({"notice_period", START_NOW})),
    ("What is your expected salary?", frozenset({"expected_ctc"})),
    ("Salary expectations (per annum)", frozenset({"expected_ctc"})),
    ("What is your current CTC?", frozenset({"current_ctc"})),
    ("Are you willing to relocate to Bangalore?", frozenset({"relocation"})),
    ("Are you legally allowed to work in India?", frozenset({"work_authorization"})),
    ("Where did you find this job posting?", frozenset({"heard_from"})),
    ("Why do you want to work at Infosys?", frozenset({"why_this_role", WHY_HIRE})),
    ("Do you own a laptop?", frozenset({LAPTOP})),
    ("Do you have a personal computer and reliable internet?", frozenset({LAPTOP})),
    ("Do you have access to a laptop and wifi?", frozenset({LAPTOP})),
    ("Can you commit to a full-time internship for 6 months?", frozenset({INTERNSHIP})),
    ("Are you available for a six-month internship?", frozenset({INTERNSHIP})),
    ("Are you okay with working night shifts?", frozenset({NIGHT_SHIFTS})),
    ("Have you built any project in React.js?", frozenset({REACT})),
    ("Do you have hands-on experience with React?", frozenset({REACT})),
    ("Why are you the right candidate for this position?", frozenset({WHY_HIRE, "why_this_role"})),
    ("Why should we select you?", frozenset({WHY_HIRE, "why_this_role"})),
    ("Introduce yourself briefly", frozenset({ABOUT_YOU})),
    ("Tell me about yourself.", frozenset({ABOUT_YOU})),
    ("Tell us about a difficult project you worked on", frozenset({HARD_PROJECT})),
    ("Are you comfortable working from the office all 5 days?", frozenset({OFFICE})),
    ("Do you have a driving licence?", frozenset({LICENSE})),
    ("Are you willing to sign a service bond of 2 years?", frozenset({BOND})),
    ("Can you join immediately?", frozenset({START_NOW, "notice_period"})),
    ("How many years of experience do you have in Java?", frozenset({JAVA_YEARS})),
    ("What are your greatest strengths?", frozenset({STRENGTHS})),
    ("How would you rate your English communication?", frozenset({ENGLISH})),
    # Look alike, but the saved answer would be wrong here.
    ("Have you worked on any project using Angular?", NONE),
    ("Have you worked with Java before?", NONE),
    ("How many years of experience do you have in Python?", NONE),
    ("What are your weaknesses?", NONE),
    ("Do you have a bike?", NONE),
    ("Are you comfortable with a fully remote role?", NONE),
    ("Do you have any prior internship experience?", NONE),
    # Nothing saved is about these at all.
    ("What is your favourite weekend hobby?", NONE),
    ("Have you done any certification in cloud computing?", NONE),
    ("What is your highest qualification?", NONE),
    ("Please share your GitHub profile link", NONE),
]
