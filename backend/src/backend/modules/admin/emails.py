"""The email an admin can send to someone who has not connected the browser
extension. The admin may rewrite the subject and the message; the button to
install the extension, the link to connect it and the footer are always added.

Every style is inline and the layout is a table, because most mail programs
ignore stylesheets.
"""

import html
from dataclasses import dataclass

DEFAULT_SUBJECT = "How is your job hunt going, {first_name}?"
DEFAULT_MESSAGE = "\n\n".join(
    [
        "Hi {first_name},",
        "Thanks for trying Rolesetu. How has it been so far? Just reply to this email and "
        "tell us. We read every reply.",
        "The Rolesetu Chrome extension is now out. It shows your match score right on "
        "LinkedIn, Naukri and Indeed job pages, and fills in application forms from your "
        "profile, so you no longer have to copy links back and forth.",
        "Install it, then open it once while you are signed in to connect it to your account.",
    ]
)

PLACEHOLDER = "{first_name}"

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
_PARAGRAPH = '<p style="margin:16px 0 0;font-size:16px;line-height:1.6;color:#3d404a">{}</p>'

_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#ffffff">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 24px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" \
style="max-width:520px;font-family:{font};color:#14151a">

<tr><td style="padding-bottom:16px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle"><img src="{site}/icon.png" width="32" height="32" \
alt="" style="display:block;border:0;border-radius:8px"></td>
<td style="vertical-align:middle;padding-left:10px;font-size:18px;font-weight:700;\
letter-spacing:-0.02em">Rolesetu</td>
</tr></table>
</td></tr>

<tr><td>{paragraphs}</td></tr>

<tr><td style="padding-top:28px">
<a href="{store}" style="display:inline-block;background:#2f5fe0;color:#ffffff;\
font-size:16px;font-weight:600;text-decoration:none;padding:12px 22px;border-radius:10px">\
Add to Chrome</a>
<p style="margin:14px 0 0;font-size:14px;line-height:1.55;color:#6b6f7b">\
Already installed? <a href="{site}/app/settings" style="color:#2f5fe0;\
text-decoration:underline">Connect it from Settings</a>.</p>
</td></tr>

<tr><td style="padding-top:32px">
<p style="margin:0;padding-top:20px;border-top:1px solid #e6e7ec;font-size:13px;\
line-height:1.55;color:#6b6f7b">\
You are getting this because you have a Rolesetu account. \
Reply "stop" and we will not email you about this again.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


def first_name(full_name: str | None) -> str:
    """The first word of the person's name, or a greeting that works without one."""
    first = (full_name or "").strip().split(" ")[0]
    return first[:40] if first else "there"


def extension_nudge(
    *, subject: str, message: str, name: str, site_url: str, store_url: str
) -> Email:
    site = site_url.rstrip("/")
    subject = subject.replace(PLACEHOLDER, name).strip()
    message = message.replace(PLACEHOLDER, name).strip()
    # The admin typed plain text: blank lines start a new paragraph.
    paragraphs = [part.strip() for part in message.split("\n\n") if part.strip()]
    html_paragraphs = "".join(
        _PARAGRAPH.format(html.escape(part).replace("\n", "<br>")) for part in paragraphs
    )
    text = (
        f"{message}\n\n"
        f"Add the extension to Chrome: {store_url}\n"
        f"Already installed? Connect it from Settings: {site}/app/settings\n\n"
        "You are getting this because you have a Rolesetu account. "
        'Reply "stop" and we will not email you about this again.\n'
    )
    return Email(
        subject=subject,
        html=_HTML.format(
            subject=html.escape(subject),
            font=_FONT,
            site=site,
            store=html.escape(store_url, quote=True),
            paragraphs=html_paragraphs,
        ),
        text=text,
    )
