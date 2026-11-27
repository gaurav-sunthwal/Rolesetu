# Backup database: daily sync and switch-over

The app has a **main** database (Neon project ApplyAgent) and a **backup** database
(Neon project db-2). Every night at 03:00 IST, `.github/workflows/db-backup.yml` makes
them equal: it copies **from whichever one changed** since the last sync, which is the
one the app is running on. Logic: `.github/scripts/db-sync.sh`.

| What changed since last sync | What the sync does |
|---|---|
| Nothing | Nothing |
| Main only (normal days) | Copies main → backup |
| Backup only (app is on the backup) | Copies backup → main |
| Both | **Copies nothing** and fails, so GitHub emails you. See "Both changed" |
| A database can't be reached (e.g. quota used up) | Nothing; tries again the next night |

How it knows what changed: after each sync it saves a fingerprint of every row in a
small `sync_meta` schema in each database (outside `public`, so it is never copied).
Each copy runs in one transaction (a failure leaves the target as it was), and the
overwritten copy is kept 3 days as the `undo-dump` artifact on the workflow run.

Secrets (already set): `MAIN_DATABASE_URL`, `BACKUP_DATABASE_URL`, plain form
`postgresql://user:pass@host/db?sslmode=require` (no `+asyncpg`).

## Switch to the backup (main is down)

1. Render → API → Environment: set `DATABASE_URL` to the backup in the app's form,
   `postgresql+asyncpg://neondb_owner:...@ep-solitary-dew-bdjo1u1v-pooler.c-8.us-east-2.aws.neon.tech/neondb?ssl=require`,
   and redeploy. Data is at most one day old.
2. Nothing else. While main is down the sync skips. Once main is back, the nightly sync
   copies everything from the backup into main.

## Switch back to main

1. Actions → db-backup → Run workflow (mode `auto`). Wait for it to say
   "copying backup → main".
2. **Right after**, set Render's `DATABASE_URL` back to main and redeploy. Anything
   written to the backup between step 1 and the redeploy would make the next sync
   report "Both changed", so keep the gap short.

## Both changed

Both databases got writes since the last sync, which usually means a switch happened
mid-day. Nothing was overwritten. Decide which one has the data you want (normally the
one the app is on now), then run the workflow with mode `main-to-backup` or
`backup-to-main` to force that direction. The other side's new rows are lost unless you
copy them by hand first. Its full copy is in that run's `undo-dump` artifact
(`pg_restore` it into a scratch database to look).

## Notes

- Each sync wakes both databases for a few minutes (about 1–2 compute-hours a month).
- Deploying a commit with a new migration while on the backup migrates the backup; the
  backup → main copy carries the schema over.
- pg_dump in the workflow is Postgres 18 (db-2 runs 18). If either server moves to a
  newer major version, bump `container:` in the workflow.
