# 0008: Shareable score cards, and approve-first social posting from the admin panel

## Context
Rolesetu is run by one person and growth has to come mostly from users
telling others. Two things help most: users showing off a good match score,
and Rolesetu posting regularly on LinkedIn, Facebook and Instagram without
someone doing it by hand every day.

## Decision
- **Shared score cards** (`modules/shares`, dashboard `/s/[slug]`). A user
  chooses to share one finished match. The card copies only the job title,
  company, score and skill names (gaps only if the user ticks the box),
  never resume text or the user's name. The link has a random 10-character
  id, can be taken down at any time, and is deleted with the account. The
  page is `noindex, follow`: it exists for social links, not for search
  results. It has its own preview image (score ring and matched skills) so
  each shared link looks good on LinkedIn, X and WhatsApp.
- **Social posting** (`modules/social`, admin `/social`). Admins connect
  accounts through each platform's official OAuth login: LinkedIn ("Share on
  LinkedIn") and Meta (Facebook Pages plus their linked Instagram business
  accounts). Tokens are encrypted with `ENCRYPTION_KEY`.
- **Approve first.** Every post starts as a draft. Scheduling it, for a time
  or for now, is the approval and is recorded in the audit log. Later
  AI-written drafts land in the same queue.
- **Direct APIs, no posting service.** It is free and keeps tokens in our own
  database. The cost is two small clients to maintain (`platforms/linkedin.py`,
  `platforms/meta.py`) and the API versions they pin.
- **Publishing runs inside the API** on a one-minute timer, like the
  feedback email. Posts are claimed with `FOR UPDATE SKIP LOCKED`, so two
  instances never publish the same one. Each account a post goes to is
  tracked on its own. A platform that is down is tried again up to 3 times.
  A request cut off mid-publish is never retried automatically, because the
  post may already be up.
- **Post images** are turned into JPEG (the only format Instagram accepts),
  stored privately in R2 and served from
  `/api/v1/public/social-images/<random id>.jpg`, because Meta downloads
  images from a public link.

## Consequences
- LinkedIn tokens last 60 days with no refresh; the panel warns 7 days ahead
  and an admin reconnects. Meta Page tokens do not expire.
- Posting to a LinkedIn company page needs LinkedIn's Community Management
  approval; only the admin's own profile is supported for now.
- Auto-publishing is on in production only (`SOCIAL_AUTO_PUBLISH` to
  override), so a laptop pointed at the shared database does not also publish.
- Instagram and Facebook image posts only work once `PUBLIC_API_URL` is the
  API's public https address.
- Setup steps: `docs/runbooks/social-posting.md`.

## Update (2026-10-27)
Scheduling a post is still the approval, but it is no longer written to an audit
log: the admin audit log was removed (see the update in ADR 0005).
