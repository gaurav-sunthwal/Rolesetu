# 2. Reading the user's Gmail to keep the tracker current

Date: 2026-10-12

## Context

Almost every company mails a candidate when an application is received, and again when
it is rejected or moves forward. Reading those mails lets the application tracker update
itself, and shows which jobs said no. Mail is the most private data the product touches.

## Decision

Code: `backend/src/backend/modules/inbox/`.

- **Access.** Google OAuth with the single scope `gmail.readonly`. The refresh token is
  encrypted with the app's Fernet key and stored in `integrations`; access tokens last
  for one sync. The consent callback has no login header, so the user is identified by
  an encrypted, ten-minute `state` value we issue.
- **What is fetched.** Only mail matching a job-related Gmail search, from the last 15
  days on first connect (`INBOX_LOOKBACK_DAYS`), then only since the previous sync.
- **What is stored.** Sender, subject, date, the kind of mail, the company and role read
  from it, and which application it was linked to (`email_messages`). The body is read
  in memory to classify the mail and is never stored. Mail that is not about one of the
  user's applications is not stored at all.
- **Classification is rules, not a model** (`classifier.py`): applied, rejected,
  interview, assessment, offer, or unclear. These mails are written from templates.
- **Updating the tracker** (`linking.py`). A mail is linked to an application by company
  name, and by role when a company has several. A status only moves forward. A mail for
  a job not yet tracked creates the application. Anything uncertain goes to a Review
  list for the user; nothing is guessed.
- **Advice** (`insights.py`) comes from patterns across rejected applications and the
  job checks attached to them (experience asked for, skills missing, score), not from
  the text of rejection mails, which rarely give a reason.
- **Mail records are served from our database, not re-read from Gmail.** Reading a
  mailbox takes over a minute and is rate limited by Google, so pages never wait on it.
  The newest 500 records per user are kept; older ones are deleted after each sync.
- **Interviews** (`schedule.py`, `interviews` table). An interview mail produces a
  scheduled interview: the time comes from the calendar invite attached to the mail when
  there is one, otherwise from the wording, read in the sender's timezone unless the mail
  names another. When no time can be read with confidence, none is stored and the user
  is asked to set it: a wrong time on a calendar is worse than none. A reminder or
  reschedule updates the same interview; a time the user set is never overwritten. Only
  the time, meeting link and place are kept, not the mail's text. Adding to a calendar is
  a Google Calendar link or a downloaded `.ics` file, built in the browser, so no
  calendar permission is requested.
- **Disconnecting** revokes the grant at Google and deletes every mail record.
  Applications stay.

## Consequences

- There is no worker yet. A sync is started by connecting, by the "Sync now" button, or
  by opening Inbox or Settings when the last sync is over 30 minutes old, and runs as an
  in-process background task. This does not survive a restart mid-sync (a sync stuck for
  10 minutes is treated as finished) and will not sync while the user is away. Moving it
  to the arq worker with a schedule is the next step.
- `gmail.readonly` is a restricted Google scope. Testing mode allows up to 100 named
  test users. A public launch needs Google's OAuth verification and a security
  assessment.
- Rules will miss unusually worded mail, most often from small companies. Those are
  either not picked up by the search or land in Review. Accuracy should be measured on
  a labelled set of real mails before launch (the spec's target is 90%).
- Advice is only as good as the job checks behind it: an application created from a
  mail alone has no job check, so its rejection cannot be explained.
