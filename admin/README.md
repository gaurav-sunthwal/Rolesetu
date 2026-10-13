# Rolesetu Admin

The private panel for running Rolesetu: who has signed up, how the product is used, the
extension waiting list, and a record of everything admins looked at. Adapted from the Phenko Mat
admin panel (layout, tables, sign-in screen).

## Run it

```bash
cp .env.example .env.local   # Firebase values are the same as the dashboard's
pnpm install
pnpm dev                     # http://localhost:3003
```

The API must list your Google account in `ADMIN_EMAILS` and allow this address in `CORS_ORIGINS`.

## How it works

- It is a separate app from the public site, so it can live on its own private address.
- It never touches the database. Every page calls the Rolesetu API (`/api/v1/admin/*`).
- **The API decides who is an admin**, on every request: a verified Google email listed in
  `ADMIN_EMAILS`. The sign-in screen here is a convenience, not the lock.
- Opening a user, opening the waiting list and deleting an account are written to the audit log.
- Not shown, on purpose: anything read from a user's Gmail, and the resume file itself.

## Pages

| Page             |                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------- |
| **Dashboard**    | Totals, 14 days of sign-ups and job checks, landing-page job links by site, paid page reads |
| **Users**        | Search by email or name; profile, job checks, applications, Gmail connected                 |
| **User**         | Profile, resume file details, recent job checks and applications; delete account            |
| **Waiting list** | Emails to write to when the extension launches; copy them all                               |
| **Audit log**    | Who opened or deleted what, and when                                                        |

After the API's admin routes change, run `pnpm gen:api-types`.
