# 5. An admin panel that goes through the API

Date: 2026-10-14

## Context

We need to see who has signed up, how the product is used, the extension waiting list, and
to help or delete an account on request. An admin panel already existed for another product
(Phenko Mat): a separate Next.js app with Google sign-in for an allow-list of emails, an
audit log, and direct database access.

## Decision

Code: `admin/` (the panel) and `backend/src/backend/modules/admin/` (its API).

- **Reused from the old panel:** the layout, tables, sign-in screen and the idea of an
  email allow-list and an audit log. Its listing, report and category pages had no
  equivalent here and were left out.
- **The panel does not touch the database.** It calls `/api/v1/admin/*`. This keeps the
  rule that the API is the only door to the data, and the panel holds no database password.
- **The API decides who is an admin, on every request:** a verified Google email listed
  in `ADMIN_EMAILS`. The panel's own sign-in check is a convenience, not the lock. With
  the list empty, nobody is an admin.
- **What an admin can see:** totals and trends; each user's profile, job checks,
  applications and details of their resume files; the waiting list.
- **What an admin cannot see:** anything read from a user's Gmail (Google's Limited Use
  rules do not allow people to read it), and the resume file itself.
- **Recorded:** opening a user, opening the waiting list and deleting an account are
  written to `admin_actions` in the same transaction.
- **Deleting an account** needs the account's email typed back. It removes the stored
  resume files and the user row, which cascades to everything else.

## Consequences

- The privacy policy no longer says a record "can be read only by you"; it says staff can
  open account data for support, that each time is recorded, and what is excluded.
- Deleting an account does not remove the Firebase sign-in, because the API has no
  Firebase admin credentials. The person could sign up again from nothing.
- Admin routes read across all users. They live in one module so that exception is easy
  to review.
