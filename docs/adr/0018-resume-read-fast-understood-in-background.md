# 18. A resume is read at once; the AI understands it in the background

Date: 2026-11-15

## Context

Onboarding asked people to wait while their resume was "read". Measured on two sample
resumes: reading it with code took 0.05 seconds; the AI's understanding (field,
headline, more skills, chunks for matching) took 34 to 38 seconds, because the
default model often timed out at 20 seconds before a backup answered. The upload
waited for all of it, then filling the profile was a second request.

## Decision

- **The upload answers with what code read** (`resumes.service.read_pdf`): name,
  contact, skills, roles, projects, education. The profile is filled in the same
  request for a new person (`POST /resume/fill`), and the PDF is stored while the
  database work runs.
- **The AI runs after the answer is sent** (`enrich_in_background`), on the fast
  models with thinking off (measured 9 to 10 seconds, with good results). It is asked
  before any lock is taken, then its findings are added under the resume's row lock:
  to the resume, and to the profile if it is already filled. It only adds: skills the
  profile lacks, and a headline and field where they are empty. It never replaces what
  the person typed. Embedding the profile for matching happens there too, in a thread.
- `resume_files.ai_status` (`pending`, `done`, `failed`) tells the dashboard where it
  is. The dashboard checks every 2 seconds while it is pending, then reloads the
  profile. If the AI fails, the profile read by code stands.
- The screens: an animated "reading" card with the real steps, then the person's own
  details appearing one after another, with a live note while the AI works.
- Tests never call the real model: `conftest._no_real_resume_ai` stubs it.

## Consequences

- Measured locally (from India to the US database): the profile appears 6.7 seconds
  after choosing the file, down from 13.4, and the AI finishes about 15 seconds later
  in the background. On the server next to the database the round trips are a few
  milliseconds, so it should be 1 to 2 seconds.
- The enrichment runs in the API process after the response. If the process stops in
  between, that resume keeps `pending` and the code-read profile; the existing field
  backfill can fill the field later.
- Someone editing their profile in the seconds before the AI finishes keeps their
  edits; the AI's skills are added alongside.
