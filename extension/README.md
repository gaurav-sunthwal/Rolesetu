# Rolesetu browser extension

Shows your match score on any job page, fills application forms from your profile, and adds
the jobs you apply to into your tracker. Built with WXT, React and Manifest V3.

## Run it locally

The API (`backend`, port 8000) and the dashboard (`dashboard`, port 3000) must be running.

```bash
pnpm install
pnpm build          # writes dist/chrome-mv3
```

Then in Chrome:

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Press **Load unpacked** and choose `extension/dist/chrome-mv3`.
3. Open the dashboard, go to **Settings**, and press **Connect extension**.
4. Open a job listing on any site. The score appears on the Apply button (or in the
   bottom-right corner when there is none). On an application form, an Autofill card appears
   in the bottom-left corner.

`pnpm dev` does the same with live reload, in a separate Chrome profile.

## How it works

| Part | File | Job |
|---|---|---|
| Detector | `entrypoints/detector.content.ts` | The only script that runs on every page. Decides whether the page is a job or an application form, and if so asks for the UI to be loaded. |
| Page reader | `lib/job-detect.ts` | Finds the job on the page: the site's `JobPosting` data first, then known selectors, then the page text. |
| Form reader | `lib/autofill/fields.ts` | Works out what each form field is asking for from its label, placeholder and name. |
| Form filler | `lib/autofill/fill.ts` | Fills empty fields from the profile. Never clicks a button. |
| Score, panel, autofill card | `entrypoints/job.content/` | Drawn inside a shadow root, so the site's CSS cannot affect it. Loaded on demand. |
| Background worker | `entrypoints/background.ts` | The only part that talks to the API. Holds the access key. |
| Dashboard bridge | `entrypoints/dashboard.content.ts` | Receives the access key from the dashboard's Settings page. |
| Popup | `entrypoints/popup/` | Connection status, and "Check this page" for a page the detector missed. |

The extension asks for access to every website, because a job can be on any company's own
pages. The detector sends nothing anywhere; page content goes to the API only once a job has
been found. Autofill never presses Submit and never replaces what you have typed.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `WXT_API_BASE_URL` | `http://localhost:8000` | Where the API is. Also the only host the extension may call. |
| `WXT_DASHBOARD_URL` | `http://localhost:3000` | Where "Open dashboard" goes. |

Before publishing, add the production dashboard address to `DASHBOARD_MATCHES` in `lib/config.ts`.
Only pages on that list can hand the extension an access key.
