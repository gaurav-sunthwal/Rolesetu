# 3. A paid page reader for job links we cannot read ourselves

Date: 2026-10-13

## Context

Checking a job from its link starts with a plain HTTP request for the page
(`safe_fetch.py`). Some job boards answer that with a block page or a sign-in wall, and
others build the listing with JavaScript, so the HTML we get has no job in it. Until the
browser extension is live, the website's link check is the main way people use the
product, so these failures matter. Running our own headless browsers and proxies would
cost more, in money and upkeep, than paying a service that already does it.

## Decision

Code: `backend/src/backend/modules/matches/fetching/rendered_fetch.py`, called from
`_load_job_page` in `modules/matches/service.py`.

- **Our own fetch always goes first.** It is free. Context.dev is called only when the
  site refused or did not answer (`PageBlockedError`: 401, 403, 429, 999, 5xx, timeout,
  unreachable), or when the page loaded but no job could be read from it.
- **No credit is spent on links that cannot be a job:** unsafe or malformed links, a
  removed listing (404/410), a non-HTML file, or a page that lists many jobs.
- **Context.dev returns the rendered HTML**, which goes through the same `read_job_page`
  as a page we fetched ourselves. Nothing else in scoring changes.
- **Keys** come from `CONTEXT_API_KEYS` (a JSON list) and are tried in order; a key that
  is refused (401, 403, 429) hands over to the next. With no keys the fallback is off.
- **Limits.** One user gets `MAX_RENDERED_READS_PER_DAY` (25) paid reads a day, counted
  from the jobs stored with `listing.reader == "rendered"`. A job read from a link is
  already reused for 24 hours, so a repeat check costs nothing.
- **Failure is quiet.** If the paid read fails for any reason, the user sees the message
  from our own fetch, which tells them to paste the description instead.

## Consequences

- A link check can now take up to about 35 seconds in the worst case (10 for our fetch,
  25 for Context.dev), inside the request. This should move to the background runner
  that the model engine already uses.
- The daily allowance counts successful reads only. Paid calls that return nothing are
  not stored, so they are logged but not counted against the user.
- The site's link is sent to a third party. Only the job link is sent, never anything
  about the user.
- Whether a given board (LinkedIn, Indeed, Naukri) can be read this way is not known
  until it is measured with real links.
