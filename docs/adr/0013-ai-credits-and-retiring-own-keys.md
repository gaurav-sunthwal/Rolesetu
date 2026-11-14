# 13. AI credits per plan, and retiring users' own Gemini keys

Date: 2026-11-15

## Context

Rolesetu now sells Pro (ADR 12). What Pro adds is more use of the features that cost
money per use: model calls. Until now there were scattered limits (5 AI answers a day,
30 resume-assistant messages per 10 minutes counted in one server's memory), and a user
could save their own Gemini key for unlimited use, which would also make any plan limit
meaningless.

## Decision

Code: `backend/src/backend/modules/credits/`.

- **One monthly allowance of AI credits per plan**: Free 30, Pro 400 (`CREDITS_PER_MONTH`),
  counted per calendar month in UTC. Costs (`COSTS`): an AI answer on a form 1, a
  resume-assistant message 1, a job check by the model engine 2.
- **Free work costs nothing**: the local scoring engine, autofill, templates, the tracker,
  and reading a resume (which keeps its own limit, so nobody is locked out of starting).
  Shared background work (domain catalogs) is not charged to anyone.
- **Spent before the call, atomically.** One SQL statement (`INSERT … ON CONFLICT DO UPDATE
  … WHERE used + cost <= limit`) both checks and spends, so parallel requests and several
  API instances can never spend past the limit.
- **Given back on failure without bookkeeping.** The spend is inside the request's
  transaction; a failed model call fails the request, which rolls back and the credit
  with it. A model-engine check runs after its request, so `run_match` gives its credits
  back when it marks the check failed.
- **402 when the allowance is used up**, with when it comes back and (on Free) the upgrade.
  The dashboard shows an Upgrade button there; the extension shows the message.
- **Plan read at spend time** (`billing.service.is_pro`): upgrading raises this month's
  limit at once; a downgrade keeps what was used.
- **Own Gemini keys are retired.** Every call uses Rolesetu's keys
  (`llm_client._candidate_keys`). `PUT /llm-keys/me` answers 410; `GET` and `DELETE` stay
  so an old key can still be seen and removed. Migration `f9b1d3e5a7c2` deletes the stored
  keys; the `user_llm_keys` table and `LLM_KEY_CHECK_TIMEOUT_SECONDS` go in a later release.
- `GET /credits/me` (dashboard and extension) returns used, left, the limit and the reset
  date. `/extension/ai-answers/usage` keeps its shape (`left`, `limit`), now in credits.

This replaces ADR 11's daily allowance of 5 answers and its own-key rules.

## Consequences

- Rolesetu pays for all model use. Worst case per month: Free 30 calls, Pro 400.
- A request holds its user's credit row locked while the model answers, so one user's
  AI requests run one after another. Different users never wait on each other.
- Users who relied on their own key are now limited by their plan.
- Extensions released before this say "free AI answers left today" for what is now a
  monthly number of credits, until they update.
