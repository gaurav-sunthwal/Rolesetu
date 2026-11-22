# Social posting: one-time setup

The admin panel's **Social** page posts to LinkedIn, Facebook Pages,
Instagram business accounts and YouTube (Shorts): text and image posts, and
reels. It schedules them, and shows each post's numbers (views, reach, likes,
shares, saves, and Instagram's average watch time). Each platform needs a
developer app once. After that, everything happens in the admin panel.

Replace `API` below with the API's public address (e.g. the Render URL).

## 1. API settings (Render)

```
ADMIN_URL=https://rolesetu-admin.vercel.app
PUBLIC_API_URL=https://API
LINKEDIN_REDIRECT_URI=https://API/api/v1/admin/social/linkedin/callback
META_REDIRECT_URI=https://API/api/v1/admin/social/meta/callback
YOUTUBE_REDIRECT_URI=https://API/api/v1/admin/social/youtube/callback
CRON_SECRET=<openssl rand -hex 32>
```

And in the admin panel (Vercel project `rolesetu-admin`): `NEXT_PUBLIC_SOCIAL_ENABLED=true`.

`ENCRYPTION_KEY` and the R2 settings must already be set (tokens are
encrypted and images are stored in R2).

## 2. LinkedIn (posts to your own profile)

1. Go to https://www.linkedin.com/developers/apps and create an app. LinkedIn
   asks for a company page to attach it to; your own Rolesetu page is fine.
2. Under **Products**, add **Sign In with LinkedIn using OpenID Connect** and
   **Share on LinkedIn**. Both are approved straight away.
3. Under **Auth**, add the `LINKEDIN_REDIRECT_URI` above as an authorized
   redirect URL.
4. Copy the Client ID and Client Secret into `LINKEDIN_CLIENT_ID` and
   `LINKEDIN_CLIENT_SECRET`.
5. If posts fail with a message about the API version, set
   `LINKEDIN_API_VERSION` to a recent month (format `YYYYMM`).

The login lasts 60 days. The Social page shows a warning a week before it
runs out; click **Connect LinkedIn** again to renew it.

## 3. Facebook Pages and Instagram

1. Instagram must be a **Business** (or Creator) account, linked to a
   Facebook Page you manage (Instagram app → Settings → Account type, then
   link the Page).
2. Go to https://developers.facebook.com/apps and create an app of type
   **Business**. Add the **Facebook Login for Business** and **Instagram**
   products.
3. In Facebook Login settings, add the `META_REDIRECT_URI` above as a valid
   OAuth redirect URI.
4. Copy the App ID and App Secret into `META_APP_ID` and `META_APP_SECRET`.
5. Leave the app in development mode. It works for accounts whose owners have
   a role on the app (you, as its admin), without Meta's app review.

When you click **Connect Facebook & Instagram**, choose your Page (and its
Instagram account) on Meta's screen. These logins do not expire.

Reel numbers (views, reach, watch time) need the `instagram_manage_insights`
permission, which the Connect button asks for. An account connected before
it was added still posts, but shows only likes and comments until you click
**Connect Facebook & Instagram** again.

## 3b. YouTube (Shorts)

1. In https://console.cloud.google.com create a project (or reuse one) and
   enable **YouTube Data API v3**.
2. **OAuth consent screen**: add the scopes `youtube.upload` and
   `youtube.readonly`, add yourself as a test user, then press **Publish app**
   ("In production"). In "Testing" the connection expires after 7 days.
   Google shows an "unverified app" warning on sign-in; continue, it is your app.
3. **Credentials → Create OAuth client → Web application**. Add the
   `YOUTUBE_REDIRECT_URI` above as an authorized redirect URI.
4. Copy the client ID and secret into `YOUTUBE_CLIENT_ID` and
   `YOUTUBE_CLIENT_SECRET`, then click **Connect YouTube** on the Social page.

Until Google audits the project ("YouTube API Services Audit"), YouTube makes
every API upload **private**. The upload works; switch the Short to Public in
YouTube Studio. Quota: 10,000 units a day; one upload costs 1,600.

## 3c. Posting on time: the hourly wake-up

Render's free plan puts the API to sleep when idle, and a sleeping API cannot
post at 8 pm. The GitHub Actions workflow `.github/workflows/social-tick.yml`
calls `POST /api/v1/internal/social/tick` every hour from 08:00 to 23:00 India
time. It posts what is due and refreshes numbers (each post at most every 6
hours, for 30 days).

1. GitHub → the repository → Settings → Secrets and variables → Actions →
   **New repository secret** `CRON_SECRET`, the same value as on Render.
2. Optional variable `API_URL` if the API is not reached through
   `https://rolesetu.vercel.app`.
3. Actions → social-tick → **Run workflow** once to check it answers 202.

A post scheduled for 20:00 goes out between 20:00 and about 20:10. Pick times
on the hour, between 08:00 and 23:00.

## 3d. Reel uploads straight to R2 (recommended)

The admin panel uploads a reel straight to R2 with a signed link, so large
files never pass through Render. The bucket must allow the admin panel's
address. In Cloudflare → R2 → the bucket → Settings → CORS policy, keep the
existing rules and add one:

```json
{
  "AllowedOrigins": ["https://rolesetu-admin.vercel.app", "http://localhost:3003"],
  "AllowedMethods": ["PUT"],
  "AllowedHeaders": ["content-type"],
  "MaxAgeSeconds": 3600
}
```

Without it, uploads still work: the panel falls back to sending the file
through the API, which is fine for ordinary reels (under ~30 MB).

## 4. Database

Migrations `c3e8a1f4d2b9` (social tables) and `e8a0c2d4f6b9` (reels, YouTube,
numbers) apply when the code containing them is deployed (`alembic upgrade
head` runs on start). Both only add tables and nullable columns.

## Using it

1. Social → **New post or reel**: write the caption, add an image or upload a
   reel (MP4, 9:16, 3–90 s), tick the accounts. YouTube asks for a title.
   **Save draft**.
2. In the **Queue**, click **Approve…** and pick a time (it defaults to the
   next 8 pm), or **Post now**. A scheduled post can be given a new time
   (**Change time**), edited, or moved back to drafts.
3. Each account shows **View post** when it is up, or the platform's reason
   if it failed. **Retry where it failed** only resends to accounts where
   it did not go up.
4. **Posted** lists what is up with each platform's numbers. The box at the
   top totals the last 7 or 30 days, with followers and average watch time;
   **Refresh numbers** reads them again now.

Reels are made on the Mac (`marketing/`, see `marketing/brand/reel-playbook.md`)
and uploaded here; Render cannot render video.
