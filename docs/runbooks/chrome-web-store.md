# Publishing the extension to the Chrome Web Store

What to build, upload and type into the Developer Dashboard. The answers below describe
what the extension does today; if its permissions or the data it sends change, change
them here and in the [privacy policy](../../dashboard/src/content/privacy.ts) too.

## Before you submit

1. The privacy policy must be live at <https://rolesetu.vercel.app/privacy>. Deploy the
   dashboard first and open the page to check.
2. Bump `version` in [extension/package.json](../../extension/package.json). The store
   refuses an upload whose version is not higher than the published one.
3. Build the package:

   ```bash
   cd extension
   pnpm typecheck && pnpm test
   pnpm zip:live      # writes dist/rolesetu-extension-<version>-chrome.zip
   ```

4. Load `dist/chrome-mv3-live` unpacked and run through the reviewer steps at the bottom
   of this page against the live site.

## Account

Register at <https://chrome.google.com/webstore/devconsole> (one-time $5 fee). Set the
publisher contact email to `gauravsunthwalwork@gmail.com` and verify it; an unverified
email blocks publishing.

## Store listing tab

| Field | Value |
|---|---|
| Name | Rolesetu |
| Summary | Taken from the manifest description. |
| Category | Workflow & Planning |
| Language | English |
| Homepage URL | `https://rolesetu.vercel.app` |
| Support URL | `https://rolesetu.vercel.app/privacy` (it carries the contact address) |

**Description**

```
Rolesetu shows how well you fit a job, right on the job page.

Open a job on LinkedIn, Naukri, Indeed or a company's careers page and Rolesetu scores it
against your resume out of 100. Every skill the job asks for is marked strong, partial or
missing, with the line from your profile that proves it, so you know whether the job is
worth an application before you spend an hour on it.

What it does
• Match score on the job page, with the skills you have and the ones you are missing.
• Autofill for application forms, from your profile and your saved answers.
• Adds the jobs you apply to into your tracker.

What it never does
• It never submits an application. You review the form and press Submit yourself.
• It never replaces something you have already typed.
• It sends nothing from pages that are not job listings or application forms.

To use it, create a free account at rolesetu.vercel.app, upload your resume, then open
Settings and press "Connect extension".
```

**Images you have to make** (the store will not accept the listing without the first two)

- Store icon, 128×128: `extension/public/icon/128.png`.
- At least one screenshot, 1280×800 or 640×400, PNG or JPEG. Suggested set: the score on
  a job page, the open panel with skills and gaps, the Autofill card on a form.
- Small promo tile, 440×280. Optional, but listings without one rank lower.

## Privacy tab

**Single purpose**

```
Rolesetu helps a job seeker apply to a job: it shows how well their resume matches the
job on the page they are viewing, fills that job's application form from their saved
profile, and records the application in their tracker.
```

**Permission justifications**

| Permission | Justification |
|---|---|
| `storage` | Stores the access key that links this browser to the user's Rolesetu account, and, for the current browser session only, the job the user is part-way through applying to. |
| `scripting` | Loads the score panel and the autofill card into a tab only after the page has been recognised as a job listing or an application form, so that nothing heavy runs on other pages. Also used when the user presses "Check this page" in the popup. Only files packaged with the extension are injected. |
| Host permissions (`http://*/*`, `https://*/*`) | Job listings and application forms are published on thousands of different company career sites and applicant tracking systems, so they cannot be listed in advance. A small script checks each page, inside the browser, for a job listing or an application form. On every other page it does nothing and sends nothing. The same permission lets the background worker call the Rolesetu API. |

**Remote code:** No. All JavaScript is inside the package.

**Data usage** (tick these)

| Category | Why |
|---|---|
| Personally identifiable information | The user's name, email, phone and city from their profile are fetched to fill application forms. |
| Authentication information | The extension stores its own access key for the user's Rolesetu account. |
| Web history | The address of each job listing the extension scores is sent and stored with the result. No other page addresses are collected. |
| User activity | A click on a job's Apply button is observed so the application can be recorded in the tracker. |
| Website content | The title, company and description of a job listing are sent to be scored. |

Leave unticked: health, financial and payment, personal communications, location.

Tick all three certifications. They are true of the code: data is not sold, is not used
for anything unrelated to the single purpose, and is not used for creditworthiness or
lending.

**Privacy policy URL:** `https://rolesetu.vercel.app/privacy`

## Distribution tab

Free, public, all regions.

## Test instructions for the reviewer

The extension does nothing until it is connected to an account, so the reviewer needs
one. Create a throwaway account with an email and password, upload a sample resume to
it, and put its login in the "Test instructions" box with these steps:

```
1. Go to https://rolesetu.vercel.app/login and sign in with the email and password above.
   A resume is already uploaded to this account.
2. Open Settings and press "Connect extension".
3. Open any job listing, for example one on linkedin.com/jobs. A match score appears on
   the Apply button, or in the bottom-right corner of the page.
4. Click the score to see the skills that matched and the ones that are missing.
5. Open an application form (for example a Greenhouse or Lever job and press Apply). An
   Autofill card appears in the bottom-left corner. It fills empty fields only and never
   submits the form.
```

## After submitting

An extension that asks for every website gets a manual review, which usually takes from a
few days to a couple of weeks. A rejection email names the policy it failed; fix that,
bump the version and upload again.

Once it is published, add the store link to the landing page and to the "install the
extension" step in the dashboard.
