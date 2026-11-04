# 9. A match score that checks more than skills

Date: 2026-10-27

## Context

A Senior Enterprise Data Architect was shown 100% for an Electrical Design Manager job.
Three things combined:

1. The score was skills matched ÷ skills found. The local engine finds skills with a
   dictionary of software and data skills, plus the names on the candidate's own profile.
   In a job outside tech it therefore finds only skills the candidate already has, so any
   such job scores close to 100. Here it found one ("Data analysis") and scored 1 of 1.
2. Nothing compared the job's line of work with the candidate's.
3. Experience counted all years, so 10.9 years of data work met "5+ years designing
   electrical systems".

A skill that was only listed also counted as fully proven.

## Decision

The score from skills is kept, and limited by checks that rule a job out whatever the
skills say. All maths stays in code; the model only reads jobs and judges skills.

- **Who scores:** the dictionary scores jobs in software and data when it recognises at
  least 3 of the job's requirements by itself. Every other job goes to the model engine
  (the user's Gemini key first, then the server's), with the model's hourly limit. Text that
  is not a job posting is turned away without a model call.
- **Field fit** (`local/fields.py`): job and role titles are sorted into fields with word
  lists. A job in a different field from every role the person has had is capped at 35.
- **Must-haves** (`local/must_haves.py`): licences, certifications, clearances and degrees
  in a named subject that the posting requires (not "preferred", not "or related field").
  A missing one is capped at 45 and listed as a gap.
- **Years in the field:** experience counts roles in the job's field or a related one.
- **Too little to check:** fewer than 3 judged requirements caps the score at 60.
- **Proof over claims:** a skill only listed, or last used in a role that ended more than
  6 years ago, is partial. A skill named in the job title counts double.
- Each limit is returned in `MatchRead.limits` with its reason, and `score_cap` is the
  lowest of them. The field verdict is `MatchRead.field_fit`.
- The new values are stored in the existing `matches.experience` JSON under `assessment`,
  so no migration is needed. Results from older rules (`local.v4`, the old model version)
  are not reused; jobs are scored again on their next check.

## Consequences

- `uv run python -m backend.evals.matching` measures it on 8 profiles × 10 jobs. Before:
  2 unrelated jobs scored 65 or more (the reported one at 100) and 3 more scored 41–64.
  After: none, and even if the model called every skill strong no unrelated job could reach
  65. With the model, the 8 same-field pairs all score 86 or more.
- Jobs outside tech now cost a model call, and take a few seconds longer.
- Scores drop for many users: listed-only skills are partial now, and limits apply.
- Field word lists will miss some titles. A title in no field changes nothing (no cap, all
  years count), so a gap in the lists makes the check do nothing rather than harm.
- Next: a judge prompt that also treats long-unused skills as partial, measured with this
  eval before and after.

## Addendum: speed, older clients and the reason line (2026-10-27)

**Older clients.** Sending jobs to the model made more checks come back `pending`. The
1.1.2 extension cannot poll, so it showed a pending check as a score of 0 with nothing
under it. `POST /matches` now follows RFC 7240: a client that sends
`Prefer: respond-async` gets the pending match at once and polls (the dashboard and the
extension from 1.1.3 do); any other client is held for up to 20 seconds and gets the
finished result. The run is never cancelled by the wait, so a slow one is still saved.

**Caching.** Three layers, all in Postgres (the API stays stateless; there is no Redis):

| Layer | Key | Saves |
|---|---|---|
| Result | user, job text hash, profile version, rules version | the whole check, when nothing changed |
| Job reading, same user | the user's job row, extract prompt version | the extract call when only the profile changed (adding a skill re-scores the job) |
| Job reading, any user | job text hash, extract prompt version | the extract call when someone else read the same posting |

A model check is two calls (read the job, judge the skills); the reading layers turn
repeat jobs into one. The shared layer reuses only what the posting itself says (role,
company, years, skills), keyed by a hash of the full text, so nothing about another user
is exposed. It is backed by `ix_jobs_content_hash`, built concurrently; the code works
without it, so the migration can run after the deploy.

Clients ask again after 0.8, 1.2, 1.5 and then every 2 seconds (the dashboard every 1.5),
instead of a flat 2 to 2.5, so a finished result is seen sooner.

**Reason line.** Every completed check carries `summary`: the reason of the limit that held
the score lowest, or else how many required skills the profile shows and which are missing.

**Tailoring.** A job title from a different field is no longer offered as the resume's
title ("Full Stack Developer" → "Mechanical Engineer" claimed work the person never did).

## Addendum: a job already seen costs nothing (2026-10-27)

- **Job id.** Links from LinkedIn, Indeed, Naukri, Internshala, Greenhouse and Lever carry
  a job id (`job_key.py`, kept in `job_json.job_key`). A repeat check of the same id, same
  profile, within 7 days returns the stored result before the page is read or compared, so
  a page whose text came out differently is not a new job. Other links are never guessed
  at: a wrong guess would show one job's result for another.
- **Each skill judged once.** On the model path, a skill the dictionary knows is judged in
  code, and a skill already judged for this profile on one of the user's last 30 checks
  reuses that verdict. Only the rest go to the model, and with none left there is no
  judging call.
- **Cost per check:** a job seen before, 0 model calls; a posting someone else already
  checked, 0 or 1 (judging only new skills); a new posting, 1 or 2.
- **Waiting.** Job-check calls give a model 15 seconds (not 30) before moving on, and a
  key that a model refused for quota is skipped on that model for a minute instead of
  being refused again on every check.
- The `ix_jobs_job_key` expression index backs the id lookups (same migration as above).
- Measured with the model eval sample: 0 false highs, same-field scores 89–100. The run
  also showed the server's Gemini keys hitting their quota (429) on most calls, which is
  where most of the waiting comes from.

## Addendum: no model call for a job outside the person's background (2026-10-27)

Before a job is handed to the model, its title's field is compared with every field the
person has worked in. When they are clearly different (and not related), the job is
answered on this machine: the field reason leads, its must-haves (licences, degrees) are
checked in code, and only skills the dictionary itself recognised are listed, so skills
found only because the person lists them are never passed off as a fit. The score is
capped at 35 like any different-field job. `MatchRead.screened` marks these results.

In the eval, unrelated pairs handed to the model went from 45 to 1 (data × accounting,
which counts as related). Same-field and related-field jobs still get the full read.

## Addendum: answer first, save after (2026-10-27)

The API runs on Railway and the database on Neon (us-east-2), so every query is a network
round trip, and a job check made about eight of them one after another. Now:

- **Measured:** every response carries `Server-Timing` (total time, database time and
  query count; see DevTools > Network > Timing), and requests over 800 ms are logged
  with that breakdown (`core/timing.py`).
- **A job seen before** is found in one query (`find_saved_result`): by its id or its text,
  with the profile's current version compared inside the query and the job joined in, so
  the profile is not loaded first. A repeat visit no longer writes anything.
- **An extension request** no longer reads the account twice: the key lookup already
  loaded it, and `resolve_user` takes it from the session.
- **A new job scored on this machine** is answered as soon as it is scored; the job and
  the result are written just after the response is sent, in their own session
  (`Started.save`). If that write fails, only the stored copy is lost: the next check
  scores the job again. The extension asks for the resume keywords once more if they
  arrive before the save, and the dashboard does not re-fetch a finished check.
- **A job the model reads** is still saved first: the background run loads it by id.
- The extension reads a newly clicked job after 0.4 s of quiet (at most 1.2 s), down
  from 0.7 s (at most 2 s).
- Still paid per request: the connection check before each request (`pool_pre_ping`,
  kept because Neon closes idle connections) and the final commit. Running the API in
  the same region as the database would make every remaining round trip much cheaper.
