# Rolesetu — Project Spec

> One place to manage your entire job hunt: know your fit for any job instantly, apply faster with autofill, and see exactly where your applications stand, automatically.

---

## 1. Main Goal

Help job seekers apply **smarter and faster**:

1. **Smarter:** an honest match score for any job, plus the skill gaps to fix.
2. **Faster:** one profile that autofills every application, with a tailored resume per job.
3. **Clearer:** a dashboard that tracks every application automatically, including replies and rejections from the inbox.

---

## 2. Product Surfaces

| Surface | What it does |
|---|---|
| **Web Dashboard** | Onboarding, profile, match results, application tracker, analytics |
| **Browser Extension** | Detects job pages, shows the match score, autofills application forms |
| **Backend + AI Service** | Resume parsing, embeddings, matching, resume tailoring, email classification |
| **MCP Server** | Lets users connect Rolesetu to Claude and query their job hunt in chat |

---

## 3. Feature List

| # | Feature | Main goal |
|---|---|---|
| 1 | **User Accounts** | Each user has a private, secure profile and data |
| 2 | **Resume Upload & Parsing** | Turn a resume PDF into structured data: skills, projects, experience, education |
| 3 | **Profile Builder** | Let users review and fix parsed data, and add extra detail the resume left out |
| 4 | **Evidence Bank (Embeddings)** | Store every project and experience as vectors so the AI can find proof for any skill |
| 5 | **Job Input (Link or Paste)** | Accept any job link or pasted JD text |
| 6 | **JD Extractor** | Turn a messy JD into clean JSON: role, company, required skills, nice-to-haves |
| 7 | **Match Score** | Give an honest, explainable fit score for the job |
| 8 | **Gap Report** | Show which skills are missing so users know what to learn |
| 9 | **Extension: Job Detection** | Recognise job pages on any website automatically |
| 10 | **Extension: Score Badge** | Show the match score right on the job page, no copy-paste needed |
| 11 | **Tailored Resume** | Generate a trimmed resume focused on the skills this job wants |
| 12 | **Autofill Applications** | Fill application forms from the saved profile so users never retype details |
| 13 | **Saved Answers Library** | Remember answers to common questions (notice period, expected CTC, relocation, "why us") |
| 14 | **Cold Email Writer** | Draft a short, tailored email to a recruiter or founder |
| 15 | **Grounding Check** | Make sure the resume and emails never claim skills the user doesn't have |
| 16 | **Application Tracker** | Record every application automatically when the user applies |
| 17 | **Inbox Scanner (Gmail)** | Read job-related emails and auto-update status: applied, replied, interview, rejected |
| 18 | **Dashboard & Analytics** | Show totals, reply rate, rejection rate, and trends over time |
| 19 | **Insights** | Point out patterns ("you get rejected most for roles needing Docker") and what to improve |
| 20 | **Follow-up Reminders** | Flag applications with no reply after X days |
| 21 | **MCP Server for Claude** | Let users ask Claude "who hasn't replied this week?" or "how am I doing this month?" |

---

## 4. User Flows

### 4.1 Onboarding
1. User signs up (Google / email).
2. Uploads resume PDF.
3. AI parses it into structured profile data → user reviews and edits.
4. User optionally adds detail per project (tech used, challenges, results) to strengthen the evidence bank.
5. Profile and evidence chunks are embedded and stored.
6. User is prompted to install the extension and (optionally) connect Gmail.

### 4.2 Checking a Job (Dashboard)
1. User pastes a job link or JD text.
2. Backend fetches the page (or uses pasted text) → JD Extractor → structured job JSON.
3. Matcher retrieves evidence for each required skill → computes score.
4. User sees: score, matched skills with evidence, gaps, and actions (Tailor resume / Draft email / Track).

### 4.3 Checking a Job (Extension)
1. User browses any job page (careers site, Greenhouse, Lever, Naukri, etc.).
2. Extension detects a job posting and sends the page text to the backend.
3. A score badge appears on the page; clicking it opens a side panel with matched skills and gaps.

### 4.4 Applying
1. User clicks **Apply** in the extension side panel.
2. Options: **Get tailored resume** (download PDF) and/or **Autofill this form**.
3. Extension fills fields from the profile and saved answers. **User reviews and clicks Submit themselves.**
4. Application is recorded in the tracker with status `applied`.

### 4.5 Status Tracking
1. If Gmail is connected, a background job scans new emails.
2. Job-related emails are matched to tracked applications and classified: `replied`, `interview`, `rejected`, `offer`.
3. Dashboard updates automatically; unmatched job emails go to a "Review" list.

### 4.6 Claude via MCP
1. User adds Rolesetu as a connector in Claude.
2. Claude can list applications, update statuses, show stats, and pull follow-up lists.

---

## 5. How Matching Works (Important)

**Don't use raw embedding similarity as the score.** Cosine similarity between any two tech documents usually lands in a narrow band (e.g. 0.70–0.85), so every job would look like a "good match." Instead:

1. **Extract** required and nice-to-have skills from the JD (structured output).
2. **Retrieve** the top evidence chunks for each skill from the user's evidence bank (vector + keyword hybrid search).
3. **Judge** each skill with the LLM: `strong` / `partial` / `missing`, quoting the evidence.
4. **Calculate** the score in code, not by the LLM:
   - Required skill: strong = 2, partial = 1, missing = 0
   - Nice-to-have: strong = 1, partial = 0.5, missing = 0
   - Score = points earned ÷ points possible × 100
5. **Adjust** for seniority mismatch (e.g. "3+ years" for a student caps the score) and show the reason.

Rule: **LLM for judgment, code for math.** Every score must be explainable.

**Extension speed:** cache scores per job URL + profile version so revisiting a page is instant and cheap.

---

## 6. Data Model (Postgres + pgvector)

| Table | Key fields |
|---|---|
| `users` | id, email, name, created_at |
| `profiles` | user_id, headline, location, links, education, version |
| `resume_files` | user_id, file_url, parsed_json, uploaded_at |
| `skills` | user_id, name, level, source (resume / user-added) |
| `evidence_chunks` | user_id, source (project / experience), text, embedding (vector), metadata |
| `saved_answers` | user_id, question_key, answer (notice period, CTC, etc.) |
| `jobs` | id, url, company, role, jd_text, job_json, fetched_at |
| `matches` | user_id, job_id, profile_version, score, skill_results_json, gaps, created_at |
| `applications` | user_id, job_id, status, applied_at, resume_version_url, contact_email, notes |
| `application_events` | application_id, type (applied / replied / interview / rejected), source (manual / gmail / extension), timestamp |
| `email_messages` | user_id, gmail_message_id, from, subject, received_at, classification, application_id |
| `integrations` | user_id, provider (gmail), encrypted_tokens, scopes, connected_at |

Store **only** the fields needed from emails (sender, subject, date, classification). Don't store full email bodies.

---

## 7. Tech Stack

| Layer | Choice |
|---|---|
| Dashboard | Next.js, TypeScript, Tailwind |
| Extension | Chrome Manifest V3, React + TypeScript (WXT or Plasmo framework) |
| Backend API | FastAPI (Python) |
| AI orchestration | LangGraph + Pydantic structured outputs |
| LLM | Cheap fast model (Gemini Flash / GPT mini-class) |
| Database | PostgreSQL (Neon) + pgvector |
| Auth | Firebase Auth (Google + email) |
| File storage | Cloudflare R2 (resumes, generated PDFs) |
| Background jobs | Worker queue (e.g. arq / Celery) for Gmail sync and parsing |
| Email | Gmail API (read-only) |
| MCP | Official `mcp` Python SDK, remote server with OAuth |
| Observability | Langfuse (LLM traces, cost, latency) + Sentry |
| Deploy | Docker; backend on Railway/Render/AWS, dashboard on Vercel |

---

## 8. Architecture

```
 Browser Extension ──┐
                     ├──► FastAPI Backend ──► LangGraph (extract / match / tailor / classify)
 Next.js Dashboard ──┤          │                        │
                     │          ▼                        ▼
 Claude (MCP) ───────┘   Postgres + pgvector         LLM API
                                ▲
                  Worker ───────┘ (Gmail sync, resume parsing)
```

---

## 9. Privacy, Safety & Compliance

- **Gmail access is a restricted Google scope.** In testing mode you can add up to 100 test users. A public launch requires Google's OAuth verification and a security assessment. Plan for this early.
- Request **read-only** Gmail access, only scan job-related emails, store minimal data, and let users disconnect and delete everything anytime.
- **Never auto-submit applications.** Autofill only; the user always clicks Submit. Auto-submitting violates many job sites' terms (e.g. LinkedIn) and risks wrong applications.
- **Never auto-send emails.** Drafts only; the user sends from their own inbox.
- **Grounding check** on every tailored resume and email: no invented skills or experience.
- Encrypt OAuth tokens at rest; isolate every query by `user_id`.
- Provide a clear privacy policy and a "delete my account and data" button.

---

## 10. Known Hard Parts

| Problem | Plan |
|---|---|
| Job sites block scraping or render with JavaScript | Extension reads the already-rendered page text; dashboard falls back to paste |
| Every application form is different | Start with standard ATS forms (Greenhouse, Lever, Ashby), then add Workday and others |
| Matching emails to the right application | Match by company domain, company name, and role; send uncertain ones to a Review list |
| Extension cost and speed | Cache scores; only score when a job page is detected |
| Tailored resume quality | Reorder and trim real content only; preview before download |

---

## 11. Build Roadmap

### Phase 1: Core AI (Weeks 1–4)
- [ ] Resume upload, parsing, profile review
- [ ] Evidence bank with embeddings
- [ ] JD input (link + paste) and JD Extractor
- [ ] Match Score + Gap Report
- [ ] Basic application tracker (manual status)
- [ ] Eval set: 20 real JDs, hand-labelled skills

### Phase 2: Extension (Weeks 5–7)
- [ ] Job page detection
- [ ] Score badge + side panel
- [ ] Autofill for Greenhouse / Lever / Ashby
- [ ] Saved Answers Library
- [ ] Auto-track on Apply

### Phase 3: Tailoring & Outreach (Weeks 8–9)
- [ ] Tailored resume generator (PDF)
- [ ] Cold email writer
- [ ] Grounding check
- [ ] Human approval step (approve / edit / regenerate)

### Phase 4: Automation & Insights (Weeks 10–12)
- [ ] Gmail connect + inbox scanner + classification
- [ ] Analytics dashboard
- [ ] Insights and follow-up reminders
- [ ] MCP server for Claude
- [ ] Langfuse tracing, Docker, deploy

---

## 12. Success Metrics

- **Skill extraction accuracy** on the 20-JD eval set (target: 90%+)
- **Email classification accuracy** on a labelled set of real job emails (target: 90%+)
- **Grounding:** 100% of claims in resumes/emails backed by evidence
- **Time saved per application** (autofill vs manual)
- **Your own results:** applications sent, reply rate, interviews landed using the tool

---

## 13. Open Questions

- Free for everyone, or free tier + paid plan later?
- Support Naukri / LinkedIn pages for scoring only (read page, no automation)?
- Which resume template(s) for tailored PDFs?
- Should insights compare users anonymously ("your reply rate vs. average")?
