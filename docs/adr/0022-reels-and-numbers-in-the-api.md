# 0022: Reels, YouTube and post numbers in the API's Social module

## Context

The marketing agent (ADR 0019) and the reel server (ADR 0020) posted reels from the
owner's Mac, so nothing went out while the Mac slept, and the numbers that decide what to
make next (average watch time, reach) were nowhere to be seen. The API already had an
admin-only Social module (ADR 0008): accounts connected through each platform's consent
screen, tokens encrypted, a queue with schedule, retry and guards against posting twice.
It only posted text and images. Hosting is free: Render's free plan (512 MB, sleeps when
idle) and Neon's free plan (100 compute-hours a month, counted while the database is awake).

## Decision

- Extend the Social module instead of moving the marketing agent: a post can carry a reel
  (an MP4 in R2) with a YouTube title and description. Instagram gets it as a reel,
  Facebook as a Page video, YouTube as a Short. LinkedIn video is refused for now.
- YouTube is a third provider, connected with Google's consent screen; the refresh token is
  stored encrypted like the others.
- Reels are uploaded from the browser straight to R2 with a signed link, then confirmed by
  the API (size, MP4 signature). Without a CORS rule for the admin panel, the panel falls
  back to uploading through the API. Instagram and Facebook download from a 2-hour signed
  link; YouTube is sent the bytes. Video is never rendered on Render.
- Each posted target keeps its platform id and numbers (views, reach, likes, comments,
  shares, saves, average watch time). They are read for 30 days, at most every 6 hours,
  plus a manual refresh. `/admin/social/stats` totals them per platform.
- Posting on time: GitHub Actions calls a secret-protected `POST /internal/social/tick`
  hourly from 08:00 to 23:00 IST, which wakes the API. "Post now" publishes immediately.
  The in-process timer checks every 10 minutes instead of every minute.

## Consequences

- ₹0. A post goes out within about 10 minutes of its hour; times outside 08:00–23:00 IST
  wait for the next wake-up.
- Every wake-up wakes Neon too. Sixteen a day is a small share of the free compute; a
  tighter schedule would not be.
- YouTube uploads stay private until Google audits the project.
- Accounts connected before `instagram_manage_insights` was requested must reconnect to
  get views and watch time.
- The marketing agent keeps making reels; posting can move to the admin panel. Its own
  posting commands still work.
