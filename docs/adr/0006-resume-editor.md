# 6. A resume editor that edits the user's own PDF, line by line

Date: 2026-10-18

## Context

People want to change their resume inside Rolesetu: reword a bullet, fix a date, drop an
old role, add a new point. Job checks already add skills and reword the headline by
editing the user's own PDF in place (ADR 0001), so the file keeps its fonts, sizes,
colours and spacing. A general editor has to keep that promise for every line.

## Decision

Code: `backend/src/backend/modules/resume_editor/` and
`dashboard/src/features/resume-editor/`, at `/app/resume`.

- **The PDF stays the source of truth.** We do not rebuild the resume from a template.
  The page is read as lines (`read_lines`), grouped under the headings they sit beneath,
  and each edit is made on the original file with the same tools as ADR 0001:
  `replace_in_line` for words, `move_down` to open or close a gap.
- **Three edits:** change a line's words, remove a line, add a line below one. Only the
  characters that differ are rewritten, so a change inside the plain part of
  "**Languages**: Go, Java" keeps the bold label. A new line copies the style, indent and
  bullet (written or drawn) of the line above it, and wraps under its own words.
- **Edits always start from the stored file.** The browser keeps the list of edits, not
  a file; every preview and the final save repeat them on the stored resume. Line ids
  are the order lines are read in, which is stable until the resume is replaced. A
  `resume_id` on every request turns a stale editor into a clear "reload" message (409).
- **Refuse rather than damage.** A change that would overflow its line, run across two
  styles, need letters no font has, or disturb other text is left out and explained next
  to the line. Lines are not added on pages laid out in columns, because moving one
  column moves the other too.
- **Live preview without a job queue.** Editing and drawing the pages takes about
  50–200 ms, so previews are plain requests, sent 500 ms after the user stops typing;
  a newer request cancels the one in flight.
- **Saving** stores the result as a new upload (re-read for the profile, counted by the
  hourly upload limit) and puts added skills on the profile, as tailoring does.

## Consequences

- Any resume Rolesetu can read can be edited, and it never looks "regenerated".
- Layout-level changes (new sections, reordering, two-column insertions) are out of
  scope; they would need a template-based editor.
- Text written with a resume's subset font can read back with odd characters (a hyphen
  as a soft hyphen). It looks right; job-site readers may see the word without the
  hyphen. The same is true of skills added by tailoring.

## Addendum: the resume assistant (2026-10-18)

A chat panel on the editor page (`/resume-editor/assist`) turns requests in plain words
("add my Rolesetu project", "put Terraform in my skills") into the same line edits.

- **No retrieval.** The whole resume (every line, with its id and how much room it has)
  and the whole profile go into one prompt: a few thousand words. Retrieving pieces by
  embedding would only add a way to miss the line the user means.
- **The model proposes, code decides.** It answers with edits to line ids
  (`ai/prompts/edit_resume.v1.md`, structured output). Code drops edits to lines that
  do not exist or were removed, and flags any skill (by the skills dictionary) or
  number in new text that appears nowhere in the user's messages, resume or profile.
- **Applied to the draft, never saved.** Unflagged edits are applied to the editor's
  draft at once, so the live preview shows them, with an undo per reply. Flagged edits
  are shown and wait for the user to confirm they are true. Saving is unchanged.
- **Keys:** the user's own Gemini key is tried first, then Rolesetu's keys (this order
  now holds for every model call, in `ai/llm_client.py`).
- **Limit:** 30 messages per user per 10 minutes, counted per server process. A soft
  cost guard only, so no database table (and no migration) was added for it.
- **Evals:** `uv run python -m backend.evals.resume_assistant` (8/8 on `edit_resume.v1`).

## Addendum: links (2026-10-18)

A PDF link is a clickable box over some words, and knows nothing about them. The editor
reads each link with the words it covers (`resume_editor/links.py`) and keeps them
together: when the words change, the box (and any drawn underline) moves onto the new
words, and an address that spelled out the old words ("github.com/old") is rewritten to
spell the new ones. A link can also be given a new address directly; addresses typed into
new lines become links; deleting the words deletes the link. The assistant sees every
link and can change one with `set_link`; an address nobody gave is held back like any
other unsupported claim. Prompt `edit_resume.v2` added this (11/11 evals).
