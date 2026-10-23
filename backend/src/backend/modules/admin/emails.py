"""The email an admin can send to someone who has not connected the browser
extension. The admin may rewrite the subject and the message; the link to
install the extension, how to connect it and the founder's sign-off are
always added after it.

It goes out as plain text from the founder, like the note in
modules/feedback: no HTML, no buttons, no footer. Mail filters treat a note
like that as one person writing to another; a designed layout is what makes
an email from a Gmail account look like a mailing and land in spam.
"""

from dataclasses import dataclass

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
