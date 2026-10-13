"""The email sent to someone who joins the waiting list.

Kept short on purpose: it confirms one thing. Every style is inline and the
layout is a table, because most mail programs ignore stylesheets.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

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
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{preview}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 24px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" \
style="max-width:480px;font-family:{font};color:#14151a">

<tr><td style="padding-bottom:32px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle"><img src="{site}/icon.png" width="32" height="32" \
alt="" style="display:block;border:0;border-radius:8px"></td>
<td style="vertical-align:middle;padding-left:10px;font-size:18px;font-weight:700;\
letter-spacing:-0.02em">Rolesetu</td>
</tr></table>
</td></tr>

<tr><td>
<h1 style="margin:0;font-size:24px;line-height:1.25;font-weight:700;\
letter-spacing:-0.02em">You are on the list</h1>
<p style="margin:16px 0 0;font-size:16px;line-height:1.6;color:#3d404a">\
Thanks for your interest in the Rolesetu browser extension. \
We will email you once, on the day it is released.</p>
<p style="margin:16px 0 0;font-size:16px;line-height:1.6;color:#3d404a">\
Until then, you can check any job against your resume on \
<a href="{site}/" style="color:#2f5fe0;text-decoration:underline">our website</a>.</p>
</td></tr>

<tr><td style="padding-top:32px">
<p style="margin:0;padding-top:20px;border-top:1px solid #e6e7ec;font-size:13px;\
line-height:1.55;color:#6b6f7b">\
We use this address only for that announcement. To be taken off the list, \
reply to this email.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


def welcome(site_url: str) -> Email:
    site = site_url.rstrip("/")
    subject = "You are on the Rolesetu extension waiting list"
    preview = "We will email you once, on the day the extension is released."
    text = (
        "You are on the list\n\n"
        "Thanks for your interest in the Rolesetu browser extension. "
        "We will email you once, on the day it is released.\n\n"
        f"Until then, you can check any job against your resume on our website: {site}/\n\n"
        "We use this address only for that announcement. "
        "To be taken off the list, reply to this email.\n\n"
        "Rolesetu\n"
    )
    html = _HTML.format(subject=subject, preview=preview, font=_FONT, site=site)
    return Email(subject=subject, html=html, text=text)
