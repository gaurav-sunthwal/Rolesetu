# 10. Reusing answers across application forms

Date: 2026-11-14

## Context

Job forms ask the same few dozen questions in endless wordings: "How soon can you join?"
is "What is your notice period?", "Do you own a laptop?" is "Do you have a laptop with a
stable internet connection?". Autofill only reused an answer when the new question had
exactly the same words, so users retyped the same answers on every site.

A first attempt (never released) embedded every saved answer, cut into chunks, on every
focus of a field. It had four problems:

1. It compared new questions with chunks of *answers*, so an essay that mentioned
   "relocate" was offered for the relocation question.
2. It re-embedded every saved answer on every request, on the API's event loop, which
   blocked the server for all users while it ran.
3. It loaded the embedding model (about 220 MB) whatever `SEMANTIC_MATCHING` said.
4. It showed raw cosine similarity to users as "88% match".

## Decision

**Compare questions with questions.** Each saved answer is known by its question: the
usual wordings for the keys the extension knows (`notice_period`...), and the words in
the key itself for the rest (`q_do_you_have_a_laptop...`). Answers are not chunked:
they are short, and their content says little about which question they answer.

**Two signals** (`saved_answers/matching.py`):

- *Words*: meaningful words after removing filler and making synonyms the same
  ("ctc", "salary", "pay" become "salary"), overlapped. Always on, free.
- *Meaning*: the embedding model's cosine similarity, when `SEMANTIC_ANSWERS=true`. It
  shares the one model instance job scoring uses, so both flags together load it once.

**Precision over recall.** A wrong answer typed into a form is worse than an empty box:

- Two questions that each name something specific the other does not, and share
  nothing specific ("…using React?" and "…using Angular?"), are never filled in.
- A yes/no question is never answered with a number saved for a "how many" one.
- Only a strong match is filled in as certain ("high"). A weaker one ("medium") is
  filled in as a draft with a dashed amber outline, and the card says how many to check.
- Users see *why* an answer was offered ("Your answer to 'How soon can you join?'"),
  never a similarity number.

**One request per form.** When a form is found, the extension sends every empty question
with no answer saved under its key to `POST /extension/answer-matches` (at most 80), once
per question key. Focusing a field makes no request: the suggestion pill reads the
scan's results. Matching runs in a worker thread, off the event loop.

**What is learned.** Questions `findFields` reads are learned as the user types, with an
Undo; written answers (textareas) included, because "Why should we hire you?" is asked
again on every form. The "Save answer" button appears only on questions `findFields`
cannot read (extra-question pop-ups, assessment steps), so nothing is saved twice.

The thresholds come from `evals/questions.py`: 39 questions against a realistic answer
bank, including look-alikes that must not match. On 2026-11-14:

| | right, filled | right, draft | missed | wrong, draft | wrong, filled |
|---|---|---|---|---|---|
| words alone | 19 | 7 | 2 | 0 | 0 |
| words + model | 23 | 5 | 0 | 1 | 0 |

The model ranked the right saved question first for every answerable case, but right
matches scored from 0.47 and wrong look-alikes up to 0.67. A score cut-off alone cannot
separate them; the word checks do.

## Consequences

- No schema change. Keys carry the question's words (cut to 56 characters), which is
  enough for matching; storing the full question text is the next step, with the
  evidence bank (below).
- Turning on `SEMANTIC_ANSWERS` costs about 220 MB of memory on the API (none extra if
  `SEMANTIC_MATCHING` is already on). Off, matching by words still reuses most answers.
- Synonym lists and stopwords need care: an eval run is required after changing them.
- **Next:** an evidence bank (profile projects, job bullets and skills as embedded
  chunks) to answer questions never answered before ("Have you built a real-time
  app?") from the profile, with template answers that need no model call; and an
  optional "Improve with AI" for written answers, the user's own key first, behind
  one per-user limit that a subscription plan can later set.
