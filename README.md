# Rolesetu

Rolesetu helps job seekers apply smarter: it scores how well you fit a job, updates your
own resume for it without changing its look, fills application forms, and keeps a tracker
of everything you applied to, updated from your Gmail.

The product spec is in [project.md](project.md). Engineering rules are in
[CLAUDE.md](CLAUDE.md). Design decisions are recorded in [docs/adr/](docs/adr/).

## What is in this repository

| Folder | What it is | Built with |
|---|---|---|
| [dashboard/](dashboard/) | The web app: profile, job checks, resume updates, applications | Next.js, TypeScript, Tailwind |
| [backend/](backend/) | The API and all the logic | FastAPI, Python 3.12, PostgreSQL |
| [extension/](extension/) | Chrome extension: score on job pages, autofill, apply tracking | WXT, React, Manifest V3 |

The dashboard and the extension only ever talk to the backend. Nothing else touches the
database.

## Run it locally

You need Node with pnpm, Python 3.12 with [uv](https://docs.astral.sh/uv/), and a
PostgreSQL database.

```bash
# Backend (port 8000)
cd backend
cp .env.example .env.local      # then fill in the values
uv sync
uv run alembic upgrade head     # create the tables
uv run uvicorn backend.main:app --reload --port 8000

# Dashboard (port 3000)
cd dashboard
cp .env.example .env.local      # then fill in the values
pnpm install
pnpm dev

# Extension
cd extension
pnpm install
pnpm build                      # then load extension/dist/chrome-mv3 in chrome://extensions
```

After the extension is loaded, open the dashboard, go to Settings and press
**Connect extension**.

## Settings

Every setting is an environment variable. The example files list them all:
[backend/.env.example](backend/.env.example) and
[dashboard/.env.example](dashboard/.env.example). Real values go in `.env.local`, which
is never committed.

| Needed for | Backend variables |
|---|---|
| Anything to work | `DATABASE_URL`, `FIREBASE_PROJECT_ID`, `ENCRYPTION_KEY`, `CORS_ORIGINS` |
| Resume upload | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` |
| Gmail sync | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `DASHBOARD_URL` |

The dashboard needs `NEXT_PUBLIC_API_BASE_URL` (where the backend is) and the
`NEXT_PUBLIC_FIREBASE_*` values from your Firebase project.

## Checks

```bash
# Backend
cd backend
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest                   # runs against the database in DATABASE_URL

# Dashboard
cd dashboard
pnpm lint && pnpm typecheck && pnpm build

# Extension
cd extension
pnpm exec tsc --noEmit && pnpm build
```

## Deploying

- **Dashboard:** any Next.js host. On Vercel, set the project's root directory to
  `dashboard` and add the `NEXT_PUBLIC_*` variables.
- **Backend:** a host that runs a long-lived Python process (not serverless), with the
  root directory set to `backend`. Run `uv run alembic upgrade head` on each release, and
  start it with `uv run uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- **After both are live:** put the dashboard's address in the backend's `CORS_ORIGINS`
  and `DASHBOARD_URL`, set `GOOGLE_REDIRECT_URI` to
  `<backend address>/api/v1/inbox/gmail/callback` and add the same address to the OAuth
  client in Google Cloud Console, and add the dashboard's domain to Firebase's authorised
  domains.
- **Extension:** build it with `WXT_API_BASE_URL` and `WXT_DASHBOARD_URL` set to the live
  addresses, and add the dashboard's address to `DASHBOARD_MATCHES` in
  [extension/lib/config.ts](extension/lib/config.ts).

## Things to know before a public launch

- Reading Gmail uses a restricted Google scope. Beyond 100 test users it needs Google's
  verification and a security assessment.
- Resume editing uses PyMuPDF, which is AGPL licensed. See
  [docs/adr/0001-edit-resume-pdf-in-place.md](docs/adr/0001-edit-resume-pdf-in-place.md).
- Gmail is only read while the dashboard is open. Reading it in the background needs a
  worker, which is not built yet.
