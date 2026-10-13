# 4. A job preview on the landing page, without signing in

Date: 2026-10-13

## Context

Until the extension is live, the website is where people meet the product, and the
landing page only described it. A visitor had to create an account and upload a resume
before seeing anything work. We wanted them to see real output first, without paying for
model calls or holding resumes for people who have no account.

## Decision

Code: `backend/src/backend/modules/previews/`, `dashboard/src/components/landing/`.

- **What the visitor gets.** They paste a job link and see the job as we read it: title,
  company, location, pay, and the skills it asks for. The skills come from the local
  skills dictionary (`parse_job`), so no model is called.
- **A locked score, with nothing behind the blur.** A score needs a profile, so none
  exists yet. The card shows the result's layout with the job's real skills, and blurred
  shapes where the score and each verdict will be. They are shapes, not hidden numbers,
  so nothing invented can be read or uncovered. Before a link is pasted the same card
  shows a worked example, labelled as one.
- **One public endpoint**, `POST /api/v1/public/job-previews`. It is the only route that
  works without a login, so it carries its own limits, all read from one table
  (`job_previews`, rows kept for a day):
  - a link already read is answered from the table, for any visitor;
  - one visitor (by hashed IP address) may have 10 new links read an hour, and failed
    reads count;
  - previews together may use the paid page reader `PREVIEW_RENDERED_READS_PER_DAY` (20)
    times a day, separate from signed-in users' own allowance.
- **Hand-off.** "See my score" stores the link in the browser's session storage. After
  sign-in the check page picks it up and scores it once there is a profile. The match
  service reuses the preview's read, so the page is not fetched (or paid for) twice.

## Consequences

- The IP address is hashed and kept one day. The privacy policy says so.
- The rate limit trusts the proxy's `X-Real-IP` / `X-Forwarded-For` header. This needs
  checking on the production host; if the header is wrong, every visitor shares one limit.
- A new visitor still has to build a profile after signing in before the score appears.
  If many drop off there, the next step is Firebase anonymous sign-in, so a resume can be
  uploaded first and the account attached afterwards.
