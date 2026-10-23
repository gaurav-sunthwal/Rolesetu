# 0007: Send email through Gmail until Rolesetu has a domain

## Context
Email went through Resend, which only delivers to real people from a domain
verified in Resend. Rolesetu has no domain yet, so only the account owner got
mail. We also want a founder's note a few hours after someone first signs
in, and there is no background worker to run timed work.

## Decision
- `core/email.py` sends through the Gmail API as one Gmail account when
  `GMAIL_SENDER_REFRESH_TOKEN` is set, else through Resend. The token comes
  from a one-time sign-in (`python -m backend.scripts.gmail_sender_token`)
  with the existing Google OAuth client and the `gmail.send` scope.
- The founder's note (`modules/feedback`) goes 3 hours after the first
  sign-in, as plain text from "Gaurav Sunthwal". People without the extension
  get a short word about it and its store link; people with it are asked how
  it has been. It runs on a 10-minute timer inside the
  API. A Postgres advisory lock lets one instance pick recipients at a time.
  Each send is recorded in `outreach_emails` (kind
  `first_use_feedback`) before it goes out, so nobody is emailed twice.
  Accounts older than 3 days are skipped.

## Consequences
- Free, about 500 recipients a day; replies land in that Gmail inbox. A
  brand-new Gmail account landed in spam, so it sends from an older account.
- The Google Cloud app must be "In production": in Testing, the sign-in
  expires after 7 days and email stops (logged as a refused sign-in).
- Gmail has no idempotency key, so a retry after a lost response could send
  twice. The feedback email avoids this by recording first.
- The timer only runs while the API is awake (Railway sleeps it when idle), so
  an email can be late but is not lost within the 3-day window.
- With a domain, set `RESEND_API_KEY`, clear the Gmail token, and change
  `EMAIL_FROM`; no code changes.
