# 16. Invite a friend, pay ₹149

Date: 2026-11-15

## Context

Rolesetu grows by word of mouth. Pro is ₹199 a month (ADR 12). Each friend a user brings
who really uses Rolesetu should make one of their months ₹149. Razorpay cannot change the
plan of a UPI subscription, which is one reason Pro is paid one month at a time: the
server sets each order's price.

## Decision

Code: `backend/src/backend/modules/referrals/`; dashboard `/app/plan`, landing `#pricing`
and `#invite`.

- **A code per user** (8 characters, no look-alike letters), made on first view. The
  invite link is `/?ref=CODE`. The site remembers it in the browser for 30 days and claims
  it once the visitor is signed in (`POST /referrals/claim`).
- **Who can be invited:** an account under 14 days old, once, by one person, never by
  themselves (also a database check). Claiming the same code again is fine; switching
  inviters is refused.
- **When a friend counts:** they have a resume on Rolesetu and 3 job checks. This is
  worked out when the referrer looks or pays, in one UPDATE.
- **The reward:** one month at `REFERRAL_AMOUNT` (₹149, never above the price on sale), at
  most one per order, INR only. `create_order` locks the oldest unlocked reward and sets it
  aside for the order. It is spent (`used_at`) only when that order is paid (checkout or
  webhook). An unpaid order does not use it up: the next order takes it. An admin refund
  gives it back.
- **Privacy:** the referrer sees each friend only as "joined", "₹149 month ready" or
  "discount used", with the join date. Nothing else about them.

## Consequences

- One friend can be farmed with a second account of one's own. That still needs a real
  resume and 3 checks, and gains ₹50 once.
- If two orders are open at once and both get paid, only one spends the reward: at most one
  extra ₹50 discount, accepted rather than adding a lock across checkout.
- The landing page and dashboard read their numbers from `content/pricing.ts`, which must
  change together with the backend constants.
