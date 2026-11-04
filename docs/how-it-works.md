# How Rolesetu works

Every app, every API call, and every flow, from the moment someone signs in.
Written from the code as of 27 Oct 2026. When something changes, update the table it is in.

---

## 1. The pieces

```
                      ┌────────────────────────┐
  Job seeker ───────▶ │ Dashboard (Next.js)    │──┐
  (browser)           │ rolesetu.vercel.app    │  │
                      └────────────────────────┘  │  Firebase ID token
                      ┌────────────────────────┐  │
  Job seeker ───────▶ │ Extension (WXT, MV3)   │──┤  Extension key (aa_ext_…)
  (on job sites)      │ Chrome / Firefox       │  │
                      └────────────────────────┘  │
                      ┌────────────────────────┐  │
  You (admin) ──────▶ │ Admin panel (Next.js)  │──┤  Firebase ID token + admin email
                      └────────────────────────┘  │
                                                  ▼
                      ┌───────────────────────────────────────────────┐
                      │ API (FastAPI, Python) on Railway  /api/v1/... │
                      │  routes → services → repositories             │
                      │  + timers inside the API (see section 8)      │
                      └───────────────────────────────────────────────┘
                         │        │         │         │          │
                         ▼        ▼         ▼         ▼          ▼
                      Postgres  Cloudflare  Gemini   Gmail API  Context.dev,
                      (Neon)    R2 (PDFs)   (LLM)    (inbox +   LinkedIn, Meta
                                                      sending)
```

| Piece | Code | Hosted on | What it does |
|---|---|---|---|
| API | `backend/` | Railway | The only thing that touches the database. Everything below calls it. |
| Dashboard | `dashboard/` | Vercel | Landing pages and the signed-in app at `/app/...`. |
| Extension | `extension/` | Chrome Web Store, Firefox | Score badge and autofill on job sites, tracks applications. |
| Admin panel | `admin/` | Vercel | Users, errors, waitlist, outreach email, social posts. |
| Database | Neon Postgres (+ pgvector) | Neon | All data. **The local `.env.local` points at production.** |
| Files | Cloudflare R2 | Cloudflare | Resume PDFs, private, served through short-lived signed links. |
| Sign-in | Firebase Auth (Google) | Firebase | The dashboard and admin panel get an ID token; the API checks it. |

Deploys are manual: `railway up` (API) and `vercel deploy --prod` (dashboard, admin). Pushing to git deploys nothing.

---

## 2. How every request proves who it is

| Caller | Sends | Checked by | Notes |
|---|---|---|---|
| Dashboard | `Authorization: Bearer <Firebase ID token>` | `core/firebase_tokens.py` → `users/dependencies.get_db_user` | Axios adds the token to every call (`dashboard/src/lib/api/client.ts`, 20 s timeout). The user row is created on the first call. |
| Extension | `Authorization: Bearer aa_ext_…` | `extension/service.py` (the key is stored as a SHA-256 hash) | Only routes using `get_db_user_or_extension` accept it: matches, tailoring, applications, extension. |
| Admin panel | Firebase ID token | `admin/dependencies.get_admin` | The Google email must be verified **and** listed in `ADMIN_EMAILS`. |
| Public pages | Nothing | n/a | `/public/...` routes only. They are rate-limited by hashed IP. |

Every user-scoped query filters by `user_id`, so one user can never read another's rows.

---

## 3. Every API route

All routes start with `/api/v1`. "Who" says which callers can use it.

### Account and settings
| Method | Path | Who | What happens |
|---|---|---|---|
| GET | `/users/me` | dashboard | The signed-in user. |
| GET / PUT / DELETE | `/llm-keys/me` | dashboard | The user's own Gemini key: status, save (encrypted, checked with a test call), remove. |
| POST | `/extension/connect` | dashboard | Issues a new extension key; any older one stops working. |
| GET | `/extension/status` | dashboard | Whether the extension is connected and when it was last used. |
| DELETE | `/extension/connection` | dashboard | Disconnects the extension. |

### Profile and resume
| Method | Path | Who | What happens |
|---|---|---|---|
| GET / PUT | `/profile/me` | dashboard | Read or save the profile. Saving bumps `profile.version`, which makes every cached score stale. |
| POST | `/resume` | dashboard | Upload a PDF. It is checked, saved to R2, and read **locally** (no AI) into a profile draft. |
| GET | `/resume/latest`, `/resume/{id}` | dashboard | The stored resume and what was read from it. |
| POST | `/resume/{id}/apply` | dashboard | Copies what was read into the profile. |
| GET | `/resume/{id}/download-link` | dashboard | A short-lived signed R2 link. |
| DELETE | `/resume/{id}` | dashboard | Removes the file and its row. |
| POST | `/public/resume-identity` | landing page | Reads name and email from a PDF so a visitor can sign up with it. The file is not kept. |
| GET / PUT / DELETE | `/saved-answers`, `/saved-answers/{key}` | dashboard | Answers to common form questions ("notice period", "relocate?"), used by autofill. |

### Job checks (match scores)
| Method | Path | Who | What happens |
|---|---|---|---|
| POST | `/matches` | dashboard, extension | Score a job from a link or pasted text. See flow 4.2. |
| GET | `/matches`, `/matches/{id}` | dashboard, extension | History, and polling a pending check. |
| POST | `/matches/{id}/share` | dashboard | Makes a public share link for a score. |
| DELETE | `/shares/{slug}` | dashboard | Turns the share link off. |
| GET | `/public/shares/{slug}` | anyone | The shared score page `/s/[slug]`. |
| POST | `/public/job-previews` | landing page | Shows what a job asks for before sign-in. No score, no AI. |

### Resume changes
| Method | Path | Who | What happens |
|---|---|---|---|
| GET | `/tailored-resumes/keywords?match_id=` | dashboard, extension | Which of the job's words the resume has, spells differently, or lacks. No AI. |
| POST | `/tailored-resumes` | dashboard, extension | Preview: a copy of the user's own PDF with the chosen skills added, words respelled, or headline changed. Nothing is saved. |
| POST | `/tailored-resumes/keep` | dashboard, extension | Repeats the same edit on the stored PDF, saves it as the new resume, and adds the skills to the profile. |
| GET | `/resume-editor` | dashboard | The resume as editable lines, grouped by section. |
| POST | `/resume-editor/preview` | dashboard | Applies the draft edits and returns page images (sent 500 ms after typing stops). |
| POST | `/resume-editor/save` | dashboard | Saves the edited PDF as a new resume. |
| POST | `/resume-editor/assist` | dashboard | The chat assistant: plain-words request in, line edits out (Gemini). 30 messages per 10 minutes. |

### Jobs page (fresh jobs)
| Method | Path | Who | What happens |
|---|---|---|---|
| GET | `/career-jobs?companies=&places=&work_modes=&include_stretch=&cursor=` | dashboard | Jobs collected from careers sites, filtered by experience, scored for this user, best first. |
| GET | `/career-jobs/companies` | dashboard | The companies followed, with job counts. |
| POST | `/career-jobs/companies` | dashboard | Add a company by its careers link. The site is read at once. 5 per user per day. |

### Application tracker
| Method | Path | Who | What happens |
|---|---|---|---|
| GET | `/applications`, `/applications/stats` | dashboard | The tracker list (paged) and counts per status. |
| POST | `/applications` | dashboard, extension | Add one. Takes an `Idempotency-Key` header so a retried click never makes two. |
| GET / PATCH / DELETE | `/applications/{id}` | dashboard, extension | Read, change status or notes, remove. |

### Gmail inbox
| Method | Path | Who | What happens |
|---|---|---|---|
| GET | `/inbox/status` | dashboard | Connected? Syncing? Last sync time. |
| GET | `/inbox/gmail/connect-url` | dashboard | Google's consent page (read-only Gmail scope). The user id travels encrypted in `state`. |
| GET | `/inbox/gmail/callback` | Google | Swaps the code for a refresh token, stored encrypted. |
| DELETE | `/inbox/gmail` | dashboard | Revokes the token and deletes every mail record. Applications stay. |
| POST | `/inbox/sync` | dashboard | Starts a sync in the background and returns `202`. The client polls `/inbox/status`. |
| GET / PATCH | `/inbox/messages`, `/inbox/messages/{id}` | dashboard | Job emails found (sender, subject, date, type only, never the body). |
| GET | `/inbox/insights` | dashboard | Patterns across outcomes ("rejections often come from X"). |
| GET / PATCH / DELETE | `/inbox/interviews`, `/inbox/interviews/{id}` | dashboard | Interviews found in email. |

### Extension only
| Method | Path | What happens |
|---|---|---|
| GET | `/extension/autofill` | Profile plus saved answers, shaped for filling forms. |
| POST | `/extension/learned-answers` | Answers the user typed into a form, saved to use next time. |
| DELETE | `/extension/learned-answers/{key}` | Forget one. |

### Public
| Method | Path | What happens |
|---|---|---|
| POST | `/public/extension-waitlist` | Join the waitlist (from the landing page). |
| GET | `/public/social-images/{name}` | Images attached to social posts, so LinkedIn and Instagram can fetch them. |

### Admin (admin panel only)
| Method | Path | What happens |
|---|---|---|
| GET | `/admin/me` | Confirms the signed-in Google account is an admin. |
| GET | `/admin/stats` | Signups, active users, checks, extension installs. |
| GET | `/admin/users`, `/admin/users/{id}` | User list and one user's detail. |
| GET | `/admin/users/{id}/resumes/{resume_id}/file` | Streams a user's resume PDF to the viewer. |
| DELETE | `/admin/users/{id}` | Deletes the account and its data, then its Firebase sign-in. |
| GET | `/admin/waitlist` | Waitlist entries. |
| GET / DELETE | `/admin/errors`, `/admin/errors/{fingerprint}` | Grouped server errors; mark one resolved. |
| GET | `/admin/users/{id}/email-templates` | Ready-made emails for that user. |
| POST | `/admin/users/{id}/email` | Sends one email to a user. |
| GET / POST | `/admin/emails/extension-nudge` | Default text, then a bulk "try the extension" email (queued). |
| GET | `/admin/social` | Connected LinkedIn and Meta accounts, and the post queue. |
| GET | `/admin/social/{provider}/connect-url`, `/callback` | Connect a LinkedIn or Meta account (OAuth). |
| DELETE | `/admin/social/accounts/{id}` | Disconnect one. |
| POST | `/admin/social/images` | Upload an image for a post. |
| GET / POST / PUT / DELETE | `/admin/social/posts`, `/admin/social/posts/{id}` | Write, edit and delete posts. |
| POST | `/admin/social/posts/{id}/schedule`, `/unschedule`, `/retry` | Queue a post for its time, take it back, or retry a failed one. |

---

## 4. The main flows, step by step

### 4.1 Sign up and first visit
1. The user clicks "Continue with Google" → Firebase signs them in and gives the browser an ID token.
2. The dashboard's first API call carries that token. `resolve_user` creates the `users` row, which also schedules the welcome email (section 8).
3. `/app/welcome` asks for a resume first, then the extension, before the dashboard shows.

### 4.2 Checking a job (the match score)
```
POST /matches {url or jd_text}
  │
  ├─ profile empty? ───────────────────────────▶ 422 "add your profile first"
  ├─ same job seen recently, same profile version? ─▶ reuse the stored result
  ├─ read the job (only when a link is given):
  │     1. safe_fetch: our own request (blocks private IPs, size-limited)
  │     2. if blocked or empty → Context.dev renders it in a real browser (paid, keys rotate)
  │     3. JSON-LD JobPosting on the page is used when present
  ├─ hourly limit per user ────────────────────▶ 429
  ├─ LOCAL engine (default, no AI, about 100 ms):
  │     dictionary of skills → requirements → judge each skill against the profile
  │     (strong = used in a role or project, or listed; partial = close substitute;
  │      missing = nothing). Embeddings may lift "missing" to "partial", never further.
  │     → done, returned at once (200)
  └─ the dictionary can't read this job → MODEL engine:
        202 "pending" → background task:
          Gemini extract_job.v1 (what the job asks for)
          Gemini judge_skills.v1 (verdict + quoted evidence per skill)
        client polls GET /matches/{id}
```
- **The score is always calculated in Python** (`matches/scoring.py`): required skills count 2 points (strong) or 1 (partial), nice-to-haves 1 or 0.5, then score = earned ÷ possible × 100. Experience can cap it at 75 or 60. The AI only gives verdicts.
- Results are cached by job and `profile.version`, so changing the profile re-scores everything.
- The dashboard sends `Prefer: respond-async` and polls. Older extensions are kept waiting up to 20 s instead.

### 4.3 Making the resume match a job
1. The check page calls `GET /tailored-resumes/keywords` → the job's skills sorted into: on your resume, written differently, or missing.
2. The user ticks only skills they really have → `POST /tailored-resumes` → a preview of **their own PDF**, edited in place (same fonts and spacing, only those words added).
3. "Replace my resume" → `POST /tailored-resumes/keep` → the same edit repeated on the stored file, saved as a new upload, and the skills added to the profile (version bump → scores refresh).
4. The Jobs page's "How to raise this score" panel uses the same two calls.

### 4.4 The resume editor and assistant (`/app/resume`)
1. `GET /resume-editor` → every line of the PDF with an id and how much room it has.
2. Edits (change, remove or add a line) are held in the browser. `POST /resume-editor/preview` replays them on the stored file and returns page images.
3. Assistant: `POST /resume-editor/assist` sends the request plus the whole resume and profile to Gemini (`edit_resume.v2`). Code then drops edits to lines that don't exist, and **flags any skill or number that appears nowhere in what the user wrote, their resume or their profile**. Flagged edits wait for the user to confirm.
4. `POST /resume-editor/save` → a new resume upload.

### 4.5 The Jobs page (fresh jobs)
1. **Once a day**, inside the API (`career_jobs/schedule.py`): each server checks hourly; the first to take the database lease collects.
2. It reads about 60 company careers sites through one reader per platform (Workday, Greenhouse, Lever, Ashby, SmartRecruiters, SuccessFactors, and some companies' own sites). It keeps jobs in India from the last 7 days, but only for experience levels some user actually has.
3. When a user opens `/app/jobs` → `GET /career-jobs`:
   - experience filter (fits, a stretch of up to 1 year more, or not stated);
   - each job scored by the local engine (no AI), cached per user, profile version and collection version;
   - work mode (remote, hybrid, on-site or not stated) read from the posting's wording;
   - score boosts: for each skill not yet strong, the points it would add.
4. "Apply" opens the company's own page **and** `POST /applications` (idempotency key `career-job:<id>`), so the job leaves the list.

### 4.6 The extension on a job site
```
detector.content.ts (every page, tiny)
  └─ looks like a job page or application form?
       └─ ask background: 'activate' → injects job.content (the real UI)
job.content
  ├─ reads title, company and description off the page
  ├─ 'check-job' → background → POST /matches (Prefer: respond-async), polls /matches/{id}
  ├─ shows the score badge, skill gaps, "add to resume" (keywords → tailor → keep)
  ├─ 'autofill-data' → GET /extension/autofill → fills the form (never submits)
  ├─ answers the user typed → 'learn-answers' → POST /extension/learned-answers
  └─ Apply click → POST /applications (status saved, Idempotency-Key ext-<matchId>)
       → once the confirmation page is seen → PATCH /applications/{id} status applied
```
- **Connecting:** the dashboard posts the key to `dashboard.content.ts` (which runs only on the dashboard) with `window.postMessage`; the key is kept in extension storage. No copy-paste.
- **Every call goes through the background worker** (`entrypoints/background.ts`): 25 s timeout, retries after 0 / 1.5 / 4 s when the server is waking up.
- Nothing runs on pages that aren't jobs, and nothing is sent from them.

### 4.7 Gmail inbox sync
1. Connect: `GET /inbox/gmail/connect-url` → Google consent (read-only) → `/inbox/gmail/callback` stores an encrypted refresh token.
2. `POST /inbox/sync` → background job: lists recent mail (`INBOX_LOOKBACK_DAYS`), skips mail already seen, classifies each one **with rules, not AI** (`inbox/classifier.py`: applied, rejected, interview, offer and so on), finds the company and role.
3. Matches each email to a tracked application (`inbox/linking.py`) and moves its status forward. Interviews are recorded on their own.
4. Only sender, subject, date and type are stored. Never the body.

### 4.8 Admin panel
- Sign in with Google → `GET /admin/me` → allowed only for `ADMIN_EMAILS`.
- Home: `/admin/stats`. Users: list, detail, resume viewer, delete account, send an email. Waitlist. AI calls. Errors (grouped by fingerprint).
- Outreach: bulk "try the extension" email (`/admin/emails/extension-nudge`), sent through Gmail from the work account.
- Social: connect LinkedIn and Instagram/Facebook, write posts, schedule them; the publisher timer (section 8) sends them.

---

## 5. Where AI is used (and where it isn't)

All model calls go through `backend/src/backend/ai/llm_client.py` (Gemini). The **user's own key is tried first**, then server key 1, then server key 2. When a model is overloaded the next model in `LLM_FALLBACK_MODELS` is tried; a failed model is skipped for 5 minutes. Every call has a timeout and retries with backoff, and is recorded for the admin panel (`modules/ai_calls`).

| Feature | AI? | Prompt file |
|---|---|---|
| Resume reading | **No**, local PDF parser (`resumes/extraction/`) | n/a |
| Job score, usual case | **No**, local dictionary + optional embeddings | n/a |
| Job score, unusual jobs | Yes | `extract_job.v1.md`, `judge_skills.v1.md` |
| Jobs page scores | **No** | n/a |
| Keyword check / add skills to resume | **No**, PDF edited in place | n/a |
| Resume assistant chat | Yes | `edit_resume.v2.md` |
| Gmail classification | **No**, rules | n/a |
| Job previews (landing page) | **No** | n/a |

---

## 6. Outside services each call can reach

| Service | Used for | Set by |
|---|---|---|
| Firebase Auth | Sign-in, token checks | `FIREBASE_*` |
| Neon Postgres | All data | `DATABASE_URL` |
| Cloudflare R2 | Resume PDFs | R2 keys |
| Google Gemini | The AI calls in section 5 | `LLM_MODEL`, `LLM_FALLBACK_MODELS`, server keys, user keys |
| Context.dev | Rendering job pages that block plain requests (paid per call) | `CONTEXT_API_KEYS` |
| Gmail API (read) | Inbox sync | `GOOGLE_CLIENT_ID/SECRET` |
| Gmail API (send) | All outgoing email, from the work Gmail account | `GMAIL_SENDER_REFRESH_TOKEN` |
| Resend | Backup email sender, for when there's a domain | `RESEND_API_KEY` |
| LinkedIn, Meta Graph | Publishing social posts | `LINKEDIN_*`, `META_*` |
| Companies' careers sites | The daily jobs collection | `career_jobs/catalog.py` |
| Sentry, Langfuse | Settings exist, **not wired up yet** | `SENTRY_DSN`, `LANGFUSE_*` |

---

## 7. Dashboard pages and the calls each one makes

| Page | Calls |
|---|---|
| `/` landing | `POST /public/job-previews`, `POST /public/extension-waitlist`, `POST /public/resume-identity` |
| `/app` overview | `/profile/me`, `/applications/stats`, `/applications` (recent), `/matches` (recent), `/extension/status` |
| `/app/welcome` | `/profile/me`, `/resume` + `/resume/{id}/apply` (resume card), `PUT /profile/me`, `/extension/status`, `/extension/connect` |
| `/app/profile` | `/profile/me`, `/resume/*`, `/saved-answers/*` |
| `/app/check` | `/matches`, `/matches/{id}`, `/tailored-resumes/*`, `/matches/{id}/share`, `/applications` |
| `/app/jobs` | `/career-jobs`, `/career-jobs/companies`, `/applications`, `/tailored-resumes`, `/tailored-resumes/keep` |
| `/app/resume` | `/resume-editor`, `/resume-editor/preview`, `/resume-editor/assist`, `/resume-editor/save` |
| `/app/applications` | `/applications/*`, `/inbox/*` |
| `/app/settings` | `/llm-keys/me`, `/extension/connect`, `/extension/status`, `/extension/connection`, `/inbox/gmail*`; "Export my data" collects `/profile/me`, `/saved-answers`, `/applications`, `/matches` into one file in the browser |
| `/s/[slug]` | `GET /public/shares/{slug}` |
| `/features/*` | None (marketing pages) |

---

## 8. Work that runs on its own, inside the API

There is no separate worker process. These start in `main.py`'s `lifespan` and run on every API server:

| Timer | File | What it does | Safe with 2+ servers because |
|---|---|---|---|
| Jobs collection | `career_jobs/schedule.py` | Hourly check; about once a day reads every careers site. | A lease row in the database: only one server collects. |
| Welcome / feedback email | `feedback/service.py` | A few hours after signup, sends one email (extension tip or "how's it going"). | The email is written to `outreach_emails` before sending, so nobody gets two. |
| Social publisher | `social/publisher.py` | Sends scheduled posts at their time, per account. | Each post and account is claimed in the database; requests cut off mid-send are never retried. |
| Embedding warm-up | `matches/local/semantic.py` | Loads the embedding model at startup so the first check is fast. | Read-only. |

Background tasks started by a request (`run_match`, `run_sync`) run in the same process after the response is sent.

---

## 9. Limits that protect cost and abuse

| What | Limit |
|---|---|
| Job checks | Per user per hour (stricter when the AI is needed) |
| Resume uploads | 10 per user per hour, size-limited PDF only |
| Resume assistant | 30 messages per user per 10 minutes |
| Adding companies to Jobs | 5 per user per day, 300 in total |
| Job previews (public) | Per hashed IP per day, and a daily cap on paid page renders |
| Extension calls | 25 s timeout, 3 tries |
| Every outside call | Has a timeout (LLM, Gmail, Context.dev, careers sites, social, email) |
