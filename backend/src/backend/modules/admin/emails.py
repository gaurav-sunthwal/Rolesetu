"""The email an admin can send to someone who has not connected the browser
extension. The admin may rewrite the subject and the message; the link to
install the extension, how to connect it and the founder's sign-off are
always added after it.

It goes out as plain text from the founder, like the note in
modules/feedback: no HTML, no buttons, no footer. Mail filters treat a note
like that as one person writing to another; a designed layout is what makes
an email from a Gmail account look like a mailing and land in spam.
"""

from dataclasses import dataclass, replace
from datetime import datetime

SENDER_NAME = "Gaurav Sunthwal"

DEFAULT_SUBJECT = "The Rolesetu Chrome extension is live"
DEFAULT_MESSAGE = "\n\n".join(
    [
        "Hi {first_name},",
        "I'm Gaurav, I built Rolesetu. Thanks for signing up.",
        "I wanted to let you know the Rolesetu Chrome extension is now live. It shows your "
        "match score right on LinkedIn, Naukri and Indeed job pages, and fills in application "
        "forms from your profile, so you don't have to copy job links back and forth.",
    ]
)

PLACEHOLDER = "{first_name}"

_ADDED = """\

You can add it here:
{store}

After installing it, open it once while you're signed in to connect it to your account.

If anything about Rolesetu has been confusing or missing, just reply. I read every reply myself.

Thanks,
Gaurav Sunthwal
Founder, Rolesetu
"""


@dataclass(frozen=True)
class Note:
    subject: str
    text: str


def first_name(full_name: str | None) -> str:
    """The first word of the person's name, or a greeting that works without one."""
    first = (full_name or "").strip().split(" ")[0]
    return first[:40] if first else "there"


def extension_nudge(*, subject: str, message: str, name: str, store_url: str) -> Note:
    subject = subject.replace(PLACEHOLDER, name).strip()
    message = message.replace(PLACEHOLDER, name).strip()
    return Note(subject=subject, text=f"{message}\n{_ADDED.format(store=store_url)}")


# --- Founder notes to one person ---------------------------------------------
# Templates the admin picks from on a user's page, filled in with what that
# person has done, so each reads like it was written to them. {first_name} is
# left in, and replaced when the email is sent.

NUDGE = "extension_nudge"
FOUNDER_NOTE = "founder_note"

_SIGN_OFF = """
Thanks,
Gaurav Sunthwal
Founder, Rolesetu
"""


@dataclass(frozen=True)
class Usage:
    """What one person has done on Rolesetu, as the templates talk about it."""

    joined_at: datetime
    job_checks: int
    applications: int
    has_extension: bool


@dataclass(frozen=True)
class Template:
    id: str
    label: str
    # When to use it, shown under its name in the panel.
    hint: str
    kind: str
    subject: str
    message: str
    recommended: bool = False


# Job checks after which someone counts as using Rolesetu a lot.
HEAVY_USE = 10


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


def _ago(then: datetime, now: datetime) -> str:
    days = (now.date() - then.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


def _paragraphs(*parts: str) -> str:
    return "\n\n".join(parts)


def templates_for(usage: Usage, now: datetime) -> list[Template]:
    """The notes that fit this person, the best fit first and marked."""
    joined = _ago(usage.joined_at, now)
    checks = _count(usage.job_checks, "job", "jobs")
    tracked = _count(usage.applications, "application", "applications")
    found: list[Template] = []

    if usage.job_checks == 0:
        found.append(
            Template(
                id="stuck",
                label="Didn't get started",
                hint="Signed up but never checked a job",
                kind=FOUNDER_NOTE,
                subject="{first_name}, did something get in the way?",
                message=_paragraphs(
                    "Hi {first_name},",
                    f"I'm Gaurav, I built Rolesetu. You signed up {joined}, but you haven't "
                    "checked a job yet, and I'd really like to know why.",
                    "Was something confusing, slow or broken? Or was it just not the right "
                    "time? Either answer helps me make it better for the next person.",
                    "Just hit reply. Even one line is enough, and I read every reply myself.",
                ),
            )
        )
    else:
        found.append(
            Template(
                id="experience",
                label="How has it been?",
                hint=f"Checked {checks}: ask what worked and what didn't",
                kind=FOUNDER_NOTE,
                subject="{first_name}, how has Rolesetu been so far?",
                message=_paragraphs(
                    "Hi {first_name},",
                    f"I'm Gaurav, I built Rolesetu. You joined {joined} and have checked "
                    f"{checks} since then. Thank you for giving it a real try.",
                    "Could I ask you two quick things?\n"
                    "1. What has been the most useful part so far?\n"
                    "2. What is one thing that annoyed you, or that you wish it did?",
                    "Just hit reply. Even one line helps, and I read every reply myself.",
                ),
            )
        )
    if usage.job_checks >= HEAVY_USE:
        found.append(
            Template(
                id="improve",
                label="What should I build next?",
                hint=f"Checked {checks}, one of the heaviest users",
                kind=FOUNDER_NOTE,
                subject="{first_name}, one question about Rolesetu",
                message=_paragraphs(
                    "Hi {first_name},",
                    f"I'm Gaurav, I built Rolesetu. I saw you've checked {checks} on it, "
                    "which makes you one of the people who use it most. Thank you.",
                    "If you could change one thing about Rolesetu tomorrow, what would it be? "
                    "A missing feature, a score that felt wrong, something slow: anything.",
                    "Your answer goes straight to the top of my list. Just hit reply.",
                ),
            )
        )
    if usage.applications > 0:
        found.append(
            Template(
                id="applications",
                label="How are applications going?",
                hint=f"Tracked {tracked}",
                kind=FOUNDER_NOTE,
                subject="{first_name}, how are your applications going?",
                message=_paragraphs(
                    "Hi {first_name},",
                    f"I'm Gaurav, I built Rolesetu. I saw you've tracked {tracked} with it. "
                    "How is it going? Any replies or interviews yet?",
                    "I'd also love to know if Rolesetu helped along the way, and where it "
                    "could have helped more: the match score, the tailored resume, the tracker, "
                    "or something else.",
                    "Just hit reply. I read every reply myself.",
                ),
            )
        )
    if not usage.has_extension:
        found.append(
            Template(
                id="extension",
                label="The extension is live",
                hint="Has not connected the Chrome extension; the store link is added",
                kind=NUDGE,
                subject=DEFAULT_SUBJECT,
                message=DEFAULT_MESSAGE,
            )
        )

    # The best fit: getting started, then applications, then general feedback.
    best = next(
        t.id
        for t in found
        if t.id in ("stuck", "applications") or (t.id == "experience" and usage.applications == 0)
    )
    return [replace(t, recommended=t.id == best) for t in found]


def founder_note(*, subject: str, message: str, name: str) -> Note:
    """A note asking for feedback: the admin's words and the sign-off, nothing else."""
    prefix = f"{PLACEHOLDER}, "
    if name == "there" and subject.startswith(prefix):
        # No name on file: "there, how has it been?" reads oddly as a subject.
        rest = subject.removeprefix(prefix)
        subject = rest[:1].upper() + rest[1:]
    subject = subject.replace(PLACEHOLDER, name).strip()
    message = message.replace(PLACEHOLDER, name).strip()
    return Note(subject=subject, text=f"{message}\n{_SIGN_OFF}")
