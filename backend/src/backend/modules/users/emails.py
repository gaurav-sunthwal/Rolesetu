"""The email that tells the people running Rolesetu someone new has signed up.

It goes to us, not to the new user, so it is plain: who, when, and how many
accounts there are now.
"""

import html
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
_ROW = (
    '<tr><td style="padding:6px 16px 6px 0;font-size:14px;color:#6b6f7b">{}</td>'
    '<td style="padding:6px 0;font-size:14px;color:#14151a">{}</td></tr>'
)


def new_user_alert(*, email: str, signed_up_at: datetime, total_users: int) -> Email:
    when = signed_up_at.strftime("%d %b %Y, %H:%M UTC")
    subject = f"New Rolesetu sign-up: {email}"
    rows = [("Email", email), ("Signed up", when), ("Accounts now", f"{total_users:,}")]
    table = "".join(_ROW.format(html.escape(label), html.escape(value)) for label, value in rows)
    return Email(
        subject=subject,
        html=(
            f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f"<title>{html.escape(subject)}</title></head>"
            f'<body style="margin:0;padding:32px 24px;background:#ffffff;font-family:{_FONT}">'
            '<p style="margin:0 0 16px;font-size:16px;font-weight:600;color:#14151a">'
            "Someone just created a Rolesetu account.</p>"
            f'<table role="presentation" cellpadding="0" cellspacing="0">{table}</table>'
            "</body></html>"
        ),
        text="Someone just created a Rolesetu account.\n\n"
        + "".join(f"{label}: {value}\n" for label, value in rows),
    )
