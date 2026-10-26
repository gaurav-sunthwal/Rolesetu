# Publishing the extension

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
| Name | From the manifest: `Rolesetu – Job Match Score, Resume Checker & Autofill` (Firefox: `Rolesetu – Job Match Score & Autofill`, as Mozilla caps names at 50 characters) |
| Summary | From the manifest description (Chrome caps it at 132 characters). |
| Category | Workflow & Planning |
| Language | English |
| Homepage URL | `https://rolesetu.vercel.app` |
| Support URL | `https://rolesetu.vercel.app/privacy` (it carries the contact address) |

**Search.** The store ranks a listing mostly on its name, summary and description, then
on installs, active users and ratings. So the words job seekers search for ("job match
score", "resume checker", "resume keywords", "ATS", "autofill job applications", "job
tracker", the job sites) are in the name, summary and the first lines of the description,
each used where it describes a real feature. Do not add a list of keywords or of sites the
extension does not support: Chrome's spam policy rejects keyword stuffing.

**Description**

```
Know if you are a good fit before you apply. Rolesetu is a job match score and resume
checker that works right on the job page: on LinkedIn, Naukri, Indeed, Internshala and
company careers pages.

Open any job listing and Rolesetu checks your resume against it, gives you a match score
out of 100, and shows the skill gaps. Every skill the job asks for is marked strong,
partial or missing, with the line from your resume that proves it. No guessing, and no
hour spent on an application that was never a fit.

WHAT YOU GET
• Job match score on every job page, with the skills you have and the ones you are missing.
• Resume keyword check: see which keywords from the job description are missing from your
  resume, the way an ATS (applicant tracking system) would.
• Tailored resume: add the skills you really have to a copy of your resume for this job,
  and download it as a PDF.
• Autofill job applications: fill application forms (including Greenhouse and Lever forms)
  from your profile, and reuse your answers to common questions.
• Job application tracker: the jobs you apply to are added to your tracker by themselves.

WHAT IT NEVER DOES
• It never submits an application. You review the form and press Submit yourself.
• It never replaces something you have already typed.
• It sends nothing from pages that are not job listings or application forms.

GET STARTED IN A MINUTE
1. Install Rolesetu. A page opens for you to upload your resume (PDF).
2. Create your free account. The extension connects by itself.
3. Open any job. Your match score appears on the Apply button.

Free for job seekers, freshers and experienced professionals, for full-time jobs and
internships.
```

**Images** (the store will not accept the listing without the first two)

- Store icon, 128×128: `extension/public/icon/128.png`.
- Screenshots, 1280×800: the four files in
  [extension/store/screenshots/](../../extension/store/screenshots/), uploaded in their
  numbered order. They show the real extension on a made-up careers page with a made-up
  candidate, so no real person or company appears in the listing. Retake them when the
  score pill, the panel or the autofill card changes.
- Small promo tile, 440×280. Not made yet. Optional, but listings without one rank lower.

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

## Firefox (addons.mozilla.org)

Listing on Firefox is free. The listing text, screenshots, privacy policy URL and reviewer
steps above are reused as they are.

```bash
cd extension
pnpm zip:firefox:live
# dist/rolesetu-extension-<version>-firefox.zip   the add-on to upload
# dist/rolesetu-extension-<version>-sources.zip   the source code Mozilla asks for
```

At <https://addons.mozilla.org/developers/> press **Submit a New Add-on**:

1. Distribution: **On this site**.
2. Upload the `-firefox.zip`. Compatibility: tick **Firefox** only, not Android.
3. "Do you need to submit source code?" **Yes**, because the code is bundled and minified.
   Upload the `-sources.zip`.
4. Categories: Search Tools, or Other. Licence: All Rights Reserved, unless you decide to
   open the code.
5. Notes to reviewer: the test account and steps from the section above, then these
   build instructions:

   ```
   Built on macOS with Node 24 and pnpm 12.
   pnpm install
   pnpm zip:firefox:live
   The add-on is written to dist/firefox-mv2-live and zipped beside it.
   The warnings about innerHTML come from the React DOM library, not from our code.
   ```

The manifest declares what the add-on sends off the device (`websiteContent`,
`browsingActivity`, `websiteActivity`) in
[wxt.config.ts](../../extension/wxt.config.ts); Firefox shows this to the user at install.
Keep it in step with the privacy policy. The add-on id there is permanent once listed.
