# 15. Payment and Pro controls in the admin panel

Date: 2026-11-14

## Context

Pro is bought one month at a time through Razorpay (ADR 12). Support needs ways to
give Pro (testers, outages), take it away, send money back, and change the price,
without a deploy and without editing the database by hand.

## Decision

- **Pro is still read only from paid rows** of `billing_orders`. A month given by an
  admin is a paid row of ₹0 (`plan = pro_grant`), so `is_pro`, credits and the plan
  page need no change. Given months are left out of the user's payment list.
- **Refunds go through Razorpay's API**, full amount, from the admin panel after a
  confirmation and a reason. The order row is locked during the call, so a second
  click waits and then finds it refunded. The request carries Razorpay's refund
  idempotency key. If the answer is lost, the payment is read back
  (`amount_refunded`) and a refund that went through is recorded, never asked again.
- **Remove** takes away one row's Pro without a refund; **End Pro** removes every
  running and upcoming row. Neither moves money.
- After a refund or removal, months that have not started yet move up behind the
  time still running, so nobody loses time they paid for.
- **Prices live in `billing_plans`**, edited in the panel: amount, days, receipt name
  and on/off sale. Read on every order (no cache), so all API instances agree at
  once. Each order stores its own `days`, so a change never alters a paid order.
  Without a row, the defaults in `plans.py` apply.
- Every change is logged in `billing_admin_actions`: who, what, why.

## Consequences

- An admin's wrong click on Refund moves real money; the confirmation names the
  amount and the person, and a reason is required.
- Partial refunds are not offered; they can still be made in Razorpay's dashboard
  (each payment links to it), but then Rolesetu's records must be updated by hand.
- Tests never edit the real `pro_month` price: they run against the shared database.
