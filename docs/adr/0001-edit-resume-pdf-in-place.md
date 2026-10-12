# 1. Tailor a resume by editing the original PDF in place

Date: 2026-10-12

## Context

Tailoring means adding skills the user confirms they have to their resume for one job.
The product promise is that the result looks exactly like the resume they uploaded.
Tools that rebuild the resume from a template cannot keep that promise: fonts, spacing
and layout all change.

## Decision

The uploaded PDF is edited directly (`backend/src/backend/modules/tailoring/pdf/`):

- New skills continue the last line of the matching row of the Skills section, in that
  line's own font, size and colour.
- When a line is full, the skill wraps to a new line and the content below is moved down
  by one line. This is done by rewriting the coordinates of the page's drawing
  instructions (`shift.py`), not by redrawing the page. An earlier attempt that placed
  two clipped copies of the page left every line in the file twice, which a job site's
  parser would read as duplicated text.
- Existing words (the headline under the name, a skill's spelling) are reworded by
  removing that one line and writing it again in the same fonts (`replace.py`). A centred
  line stays centred. Every other line on the page is compared before and after, and the
  change is refused if anything else was disturbed.
- Job titles the user actually held, employers and dates are never edited. A suggested
  headline stays within the same kind of role and never gains seniority the resume does
  not already claim (`keywords.py`).
- Text is never shrunk or squeezed. A skill that does not fit is reported as not added.
- Which row a skill goes in comes from the skills dictionary. No model is called.
- The font is, in order: the same standard PDF font, the resume's own embedded font if
  it contains every letter needed, or a look-alike with the same letter widths found on
  the machine (`FONT_DIR`, then the system font folders).
- The result is read back with the resume parser to confirm each skill can be found.
- Building the updated file is a preview: it is returned in the response and nothing is
  stored or changed. "Save as my resume" is a second call that sends the same choices
  (not the file); the server repeats the edit, replaces the saved resume, and adds the
  new skills to the profile. The resume and the profile therefore change together, so a
  job score never counts a skill the saved resume does not show. Storage per user stays
  at one resume.

Libraries: PyMuPDF for reading layout, writing text and rendering previews; pikepdf for
parsing and re-serialising the drawing instructions.

## Consequences

- PyMuPDF is AGPL. Running it in a hosted, closed-source product needs a commercial
  licence from Artifex, or the PDF code must move to permissively licensed libraries
  (pikepdf + fontTools). This must be settled before launch. All PyMuPDF use is inside
  `modules/tailoring/pdf/` and `tailoring/service.py` to keep that move contained.
- A Linux server needs the look-alike fonts installed (Liberation, Carlito, Caladea,
  Gelasio, DejaVu) or added to `FONT_DIR`; without them, a skill whose letters are
  missing from the resume's embedded font is reported as "no font".
- Not supported yet: Skills sections with one skill per line or in bullet lists, pages
  with a second column beside the Skills section when a new line is needed, scanned
  resumes, and rewriting the summary.
