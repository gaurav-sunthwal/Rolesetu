# 12. Paying for Pro with Razorpay's standard checkout

Date: 2026-11-14

## Context

Rolesetu adds a paid plan, Pro, at ₹199 a month. Most users are in India, where UPI is
how people pay. Razorpay takes UPI, cards, net banking and wallets, and international
cards once the account is approved for them. Stripe is invite-only for new Indian
businesses.

Razorpay's subscriptions (autopay) cannot change the plan of a UPI-authorised
subscription, which the planned referral price (₹149 in a month the user brought a
friend) would need. A payment per month avoids that: the server sets each month's
price when the order is made.

## Decision

Code: `backend/src/backend/modules/billing/`, dashboard `features/billing/`.

- **One payment buys one month** (`plans.PRO_MONTH`, 30 days). No autopay. Paying again
  adds a month after the current one. The next month can be bought in the last
  `RENEW_WITHIN_DAYS` (7) days, so nobody pays twice by mistake.
- **The server sets the price.** The browser asks for a plan by name; the amount and
  currency come from `plans.py`.
- **Pro is given only when Razorpay confirms it.** `POST /billing/orders/verify` checks
  the checkout's signature (HMAC-SHA256 of `order_id|payment_id` with the key secret,
  compared in constant time), then fetches the payment from Razorpay and requires it
  to be captured, for this order, for the full amount and currency. An authorised
  payment is captured first.
- **The webhook is the safety net** (`POST /billing/webhooks/razorpay`, events
  `order.paid` and `payment.captured`). It checks `X-Razorpay-Signature` over the raw
  body with `RAZORPAY_WEBHOOK_SECRET`, then settles exactly as verify does. Without
  the secret it refuses every call.
- **Settling happens once.** A per-user advisory lock, then a row lock on the order,
  serialise the checkout and the webhook. A paid order is never paid again, and a
  payment id is unique across orders.
- **Pro is derived, not stored.** A user is Pro while now falls in a paid order's
  `[pro_starts_at, pro_ends_at)`. `billing.service.is_pro` is what plan limits read.
- **Scoped to the user.** Orders are looked up by the caller's id; someone else's
  order is "not found". Only dashboard sessions can buy (not extension tokens).
- **Razorpay is called with httpx**, not its SDK (which is synchronous). Every call
  has a timeout; only reads are retried. Razorpay refusing our keys is a 503, never a
  401, which the dashboard would read as signed out.

## Consequences

- People renew by hand each month. The dashboard shows when Pro ends; reminder emails
  are still to do.
- Plan limits (AI credits for Free and Pro) are not enforced yet. They must ship
  before live payments are switched on, or Pro sells nothing.
- Deleting an account deletes its orders (`ON DELETE CASCADE`). Invoices for tax are
  Razorpay's records; check with an accountant whether Rolesetu must keep its own.
- International cards need Razorpay's approval of the account, and a USD price.
- Live keys go only into Railway's environment. The test keys used in development
  were shared in a chat and must never be promoted to live.
