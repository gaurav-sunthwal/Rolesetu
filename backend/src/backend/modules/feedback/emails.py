"""The note sent once, a few hours after someone first signs in, from the
founder. It comes in two versions:
- the person has not connected the browser extension: thanks, and a short
  word about what the extension does, with its Chrome Web Store link;
- they have: thanks, and how has it been so far.

Both are plain text with no HTML, no footer and no unsubscribe header, and at
most one link. A note like that looks like what it is, one person writing to
another, and mail filters treat it that way; layouts, links and footers are
what make an email look like a mailing.
"""

from dataclasses import dataclass

SENDER_NAME = "Gaurav Sunthwal"

_SIGN_OFF = """\
Thanks,
Gaurav Sunthwal
Founder, Rolesetu
"""

WITHOUT_EXTENSION_SUBJECT = "Thanks for trying Rolesetu"
_WITHOUT_EXTENSION = """\
Hi {name},

I'm Gaurav, I built Rolesetu. Thanks for trying it today.

One thing you might not know: Rolesetu also has a Chrome extension. It shows \
your match score right on LinkedIn, Naukri and Indeed job pages, and fills in \
application forms from your profile, so you don't have to copy job links back \
and forth.

You can add it here:
{store_url}

After installing it, open it once while you're signed in to connect it to \
your account.

And if anything so far felt confusing or missing, just reply. I read every \
reply myself.

"""

WITH_EXTENSION_SUBJECT = "How has Rolesetu been so far?"
_WITH_EXTENSION = """\
Hi {name},

I'm Gaurav, I built Rolesetu. Thanks for using it, and for setting up the \
extension too.

How has it been so far? Was anything confusing, slow, or missing? Even a \
one-line reply helps me a lot. I read every reply myself.

"""


@dataclass(frozen=True)
class Note:
    subject: str
    text: str


def _personal(subject: str, first_name: str) -> str:
    """The subject with the first name in front, or as it is without a name."""
    return f"{first_name}, {subject[0].lower()}{subject[1:]}" if first_name else subject


def first_use_feedback(*, full_name: str | None, has_extension: bool, store_url: str) -> Note:
    first_name = (full_name or "").strip().split(" ")[0][:40]
    name = first_name or "there"
    if has_extension:
        return Note(
            subject=_personal(WITH_EXTENSION_SUBJECT, first_name),
            text=_WITH_EXTENSION.format(name=name) + _SIGN_OFF,
        )
    return Note(
        subject=_personal(WITHOUT_EXTENSION_SUBJECT, first_name),
        text=_WITHOUT_EXTENSION.format(name=name, store_url=store_url) + _SIGN_OFF,
    )
