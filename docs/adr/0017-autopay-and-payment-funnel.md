# 17. Autopay, the payment funnel, and payment reminder emails

Date: 2026-11-15

## Context

Pro was paid one month at a time (ADR 12), so people had to remember to come back and
pay. The owner wants monthly autopay, a detailed view of where people stop on the way to
paying and why payments fail, and an email to people who leave the payment halfway.

## Decision

Code: `backend/src/backend/modules/billing/` (`subscriptions.py`, `funnel.py`,
`funnel_admin.py`, `reminders.py`); dashboard `features/billing/`; admin
`/payment-funnel`.

**Autopay (Razorpay Subscriptions)**

- "Start autopay" is the main way to buy Pro. The server makes the subscription at the
  price on sale, on a Razorpay plan made for that exact price (`billing_razorpay_plans`):
  a plan's amount can never change, so a new price gets a new plan and existing
  subscribers keep theirs. Nothing can start while Pro is off sale.
- Someone already on Pro starts autopay with `start_at` = the end of their paid time, so
  nobody is charged twice. A mandate made but never approved is reused for a day.
- Pro is still only ever given by a paid `billing_orders` row: each monthly charge
  becomes one, after Razorpay confirms the payment is captured and its invoice names
  this subscription. Pro runs from the charge's `current_start` to `current_end` plus a
  day of grace. A charge is recorded once (its payment id is unique), whichever of the
  checkout and the `subscription.charged` webhook comes first.
- The subscription's state is only copied from Razorpay (`fetch_subscription`), never from
  the browser or the webhook body. The checkout proof is HMAC(`payment_id|subscription_id`).
- Cancelling sets `cancel_at_cycle_end`: no more charges, the paid month keeps running.
  Autopay can be started again; it begins when the paid time ends.
- An admin refund, removing a month or ending Pro, and deleting an account all stop
  autopay first (`stop_all`). If Razorpay cannot confirm the stop, nothing else happens,
  so nobody is charged for Pro they no longer have.
- A one-month payment (ADR 12) stays as a small "pay for one month instead" link for
  banks and cards that cannot do autopay. It is refused while autopay is on.
- Referral (ADR 16): with a reward, autopay is made with `RAZORPAY_REFERRAL_OFFER_ID` (a
  Dashboard offer: flat ₹50 off the first payment), so the first charge is ₹149. The
  reward is spent on that first charge. Without the setting, the price is ₹199.

**Payment funnel** (`billing_funnel_events`)

- The dashboard reports what only it sees: the plan page, the upgrade click, the payment
  window opened or closed, each failed try with Razorpay's code and description, a
  successful payment, a check that failed. Steps are an allow-list; details are a few
  short, flat values (never card or account numbers); 120 events an hour per user.
- The server adds orders and mandates made, Razorpay unreachable, and failed checks
  (written in their own transaction so a failing request cannot roll them back), and
  every `subscription.*` webhook.
- Admin `/payment-funnel`: people per step with conversion, top failure reasons, autopay
  outcomes, and everyone who left halfway with their last step, error and reminder, each
  opening to their full timeline.

**Reminder emails** (on a 10-minute timer inside the API, like ADR 7's note)

- Opened the payment window, nothing paid since, not on Pro: one email an hour later
  (`PAYMENT_REMINDER_AFTER_MINUTES`), at most once a week, not for drop-offs older than
  48 hours.
- An autopay renewal Razorpay is retrying or gave up on: one email to update the payment
  method, at most once a week.
- Recorded in `outreach_emails` before sending; an advisory lock lets one instance send.

## Consequences

- Razorpay Subscriptions must be enabled in Live mode, and the webhook must send the
  `subscription.*` events (authenticated, activated, charged, pending, halted, cancelled,
  completed) as well as `order.paid` and `payment.captured`.
- Changing the price affects new subscribers only.
- Emails still go out through the Gmail account (ADR 7), which bounces some automated
  mail; a domain with Resend is needed for reminders to arrive reliably.
- A test or support case where Razorpay no longer has a subscription blocks deleting
  that account until the row is fixed by hand: refusing is safer than risking a charge.
