# 14. Following installs before sign-in

Date: 2026-11-14

## Context

The Chrome Web Store reported 432 installs in 30 days (76% from Romania) while only
16 accounts exist. Extension events were sent only once a browser was connected to an
account, so an install that never signed in left no trace: we could not tell a person
who gave up at the sign-up page from a bot that never opened a page.

## Decision

- Each install makes a random id for itself (`local:installId`). Until it is connected,
  its events go to `POST /extension/installs/events` with no account, along with what
  the browser says about itself: version, browser, OS, language, time zone.
- The setup link carries `?install=<id>`; the website's setup pages report the steps
  only they see: page loaded, sign-up started (and how), sign-in failed (Firebase's
  error code), signed in, automatic connect failed. With no id in the link, the page
  asks the extension (the bridge's `present` reply carries it before connecting).
- `runtime.setUninstallURL` points at `GET /extension/installs/{id}/uninstalled`, which
  records the removal once and redirects to `/goodbye`, where one optional click says why.
- On connecting, authenticated batches carry the install id, linking the install (and
  its journey) to the account. An install already linked to another account is kept.
- Stored apart from `ext_events` (`ext_installs`, `ext_install_events`) so the existing
  per-user analytics are unchanged. No address is stored, only a hash used for limits
  (200 new installs per address an hour, 300 events per install a day) and to show
  installs that share an address.
- Admin: an Installs page with the funnel, breakdowns, signs of bots (automated
  browser, many installs from one address, never did anything) and each install's
  journey.
- Switching analytics off in the popup stops all of it, including the uninstall count.

## Consequences

- Only installs of the version that ships this are followed; the store's figures
  before that cannot be explained after the fact.
- Time zone tells VPN users (real time zone, foreign address) from machines in the
  country itself, which the store's per-country count cannot.
- Records not linked to an account are deleted 90 days after they were last updated.
