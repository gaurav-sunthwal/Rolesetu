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

## Hosting

Live at https://rolesetu-admin.vercel.app (Vercel project `rolesetu-admin`). Deploy with
`vercel deploy --prod --yes` from this folder. The `NEXT_PUBLIC_*` values are set in the Vercel
project. The address must also be listed in the API's `CORS_ORIGINS` (Railway) and in Firebase
Authentication's authorized domains, or Google sign-in fails.

## How it works

- It is a separate app from the public site, so it can live on its own private address.
- It never touches the database. Every page calls the Rolesetu API (`/api/v1/admin/*`).
- **The API decides who is an admin**, on every request: a verified Google email listed in
  `ADMIN_EMAILS`. The sign-in screen here is a convenience, not the lock.
- Not shown, on purpose: anything read from a user's Gmail, and the resume file itself.

## Pages

| Page                 |                                                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Dashboard**        | Totals, 14 days of sign-ups and job checks, landing-page job links by site. Every count opens the list behind it |
| **Activity**         | Sign-ups, job checks and applications per day for any dates (up to a year); each day opens its list              |
| **Users**            | Search by email or name; filter by profile, extension, Gmail, day joined                                         |
| **User**             | Profile, resume file details, recent job checks and applications; delete account                                 |
| **Job checks**       | Every user's job checks; filter by period and paid page reads                                                    |
| **Applications**     | Every application users are tracking                                                                             |
| **Landing previews** | Job links pasted on the landing page in the last day; filter by site, failed, paid                               |
| **Paid page reads**  | Pages read through the paid reader, by users and by visitors                                                     |
| **AI calls**         | Every model call: where it came from, who it was for, tokens, time                                               |
| **Waiting list**     | Emails to write to when the extension launches; copy them all                                                    |
| **Errors**           | What went wrong, grouped by problem                                                                              |

After the API's admin routes change, run `pnpm gen:api-types`.
