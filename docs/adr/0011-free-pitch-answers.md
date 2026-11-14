# 11. Pitch answers written without a model

Date: 2026-11-14

## Context

Every application asks some form of "What interests you about working for this
company?", "Why should we hire you?", "Tell us about yourself" or "Write a note to the
founder". Reusing one saved answer everywhere (ADR 10) names the last company and says
nothing about this job. A model call per answer would personalise it, but Rolesetu is
meant to stay free to run, so a paid call per form is not the default.

Training a model on profile data was considered and rejected: one profile is far too
little data to learn writing from, a model trained across users could put one person's
facts in another's answer, and serving it would need GPUs.

## Decision

**Layer 1, now: written from the user's own data, in code** (`modules/pitch/`).

- The question's kind is read with word patterns (`pitch_kind`).
- The user's own saved answer comes first. The extension saves written answers with
  this job's company and role names replaced by `{company}` and `{role}`; the next job's
  names go back in (`fill_template`, `fillTokens`). An answer serves every question of
  its kind, however worded.
- Without one, `compose` fills a short template: the profile's skills this job names
  (in the order the job names them), the project and the role bullet that best show
  them, the company and role names, and the founder's first name when the question
  gives it.
- Every fact comes from the profile. The posting only orders the facts; its text is
  never copied into an answer, so instructions hidden in it have nothing to act on.
- Answers are filled as drafts (dashed amber) with where they came from, never sent.

`POST /extension/pitch-answers` takes up to 10 questions per form with the job's names
and text, and makes no model call.

**Layer 2, next: natural wording on the user's device.** Chrome's built-in model
(Gemini Nano, Prompt API, stable for extensions) can reword the Layer 1 draft on the
user's machine: no cost to Rolesetu, nothing leaves the device. The reworded text is
kept only if it adds no names or numbers the draft did not have. Where the browser has
no model, Layer 1's draft is used as it is.

**On request: "Write with AI" / "Improve with AI"** (`modules/pitch/ai_answers.py`,
prompt `write_answer.v1`). For a box nothing above could fill, or to improve what is in
it, the user may ask the model. It fills the box as a draft; it never submits.

- *(Superseded by ADR 13: answers now spend monthly AI credits, and own keys are retired.)*
- Free: 5 a day per user (UTC), on Rolesetu's key, Generate and Improve together
  (`FREE_AI_ANSWERS_PER_DAY`, the one place a paid plan will change). Counted from the AI
  calls log, so it holds across API instances.
- With their own Gemini key, unlimited: their key is tried first. Past the free 5, the
  call may use only their key (`allow_server_keys=False`), so a failing key never falls
  back to unlimited use of Rolesetu's.
- Every sentence naming a number, link or skill found nowhere in the profile, the job
  or the user's own text is removed before the answer is returned. If nothing is left,
  the user is asked to type it.
- Facts only the user knows (notice period, salary, date of birth...) get no AI button.
  The button appears only with a reason: a written answer (a multi-line box, or an open
  question), inside an application, never on search boxes, filters or pickers.
- Speed: answers use `fast_llm_models` with thinking off and an 8s wait per model. On
  2026-11-14 one answer took 2.0s on gemini-2.5-flash without thinking, while the default
  model (gemini-flash-latest) had not answered after 45s. The profile shown to the model is
  cut to what the job is about (`focused_profile`); claims are still checked against all of it.
- The extension sends it once, with a longer timeout and no retry, so one click is
  never two paid calls.

## Consequences

- Free and instant for every user; nothing to scale on the server beyond a few
  milliseconds of string work per form.
- Answers are correct and specific but plain, and long resume bullets make them long.
  Layer 2 is what makes them read naturally.
- Templates assume English and resume-style descriptions (a title line, then bullets
  that start with a verb). Profiles written otherwise get the simpler sentences.
- Saved templates show `{company}` and `{role}` on the dashboard's Saved answers.
