# Social posting: one-time setup

The admin panel's **Social** page posts to LinkedIn, Facebook Pages and
Instagram business accounts. Each platform needs a developer app once. After
that, everything happens in the admin panel.

Replace `API` below with the API's public address (e.g. the Railway URL).

## 1. API settings (Railway)

```
ADMIN_URL=https://<admin panel address>
PUBLIC_API_URL=https://API
LINKEDIN_REDIRECT_URI=https://API/api/v1/admin/social/linkedin/callback
META_REDIRECT_URI=https://API/api/v1/admin/social/meta/callback
```

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

## 4. Database

Apply migration `c3e8a1f4d2b9` (match shares + social tables) **after** the
code containing it is deployed (see the deploy notes: Railway runs
`alembic upgrade head` on start, so deploying the code applies it).

## Using it

1. Social → **New post**: write the text, add an image (Instagram needs
   one), tick the accounts, **Save draft**.
2. In the **Queue**, click **Approve…** and pick a time, or **Post now**.
3. Each account shows **View post** when it is up, or the platform's reason
   if it failed. **Retry where it failed** only resends to accounts where
   it did not go up.
