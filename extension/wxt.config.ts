import { readFileSync } from 'node:fs';

import { defineConfig } from 'wxt';

// `pnpm build:live` sets WXT_LIVE. The live addresses in .env.live are then
// loaded here, so the build is an ordinary release build (minified) that just
// points somewhere else, and it is written beside the local one instead of over it.
const live = process.env.WXT_LIVE === '1';
if (live) {
  for (const line of readFileSync('.env.live', 'utf8').split('\n')) {
    const match = /^([A-Z_]+)=(.+)$/.exec(line.trim());
    if (match?.[1] && match[2]) process.env[match[1]] = match[2];
  }
}

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  // A visible folder name: macOS hides dot-folders in Chrome's "Load unpacked" picker.
  outDir: 'dist',
  outDirTemplate: live
    ? '{{browser}}-mv{{manifestVersion}}-live'
    : '{{browser}}-mv{{manifestVersion}}',
  manifest: ({ browser }) => ({
    name: 'Rolesetu',
    description:
      'See your match score on any job page, fill application forms from your profile, and track the jobs you apply to.',
    permissions: ['storage', 'scripting'],
    // Every site: a job can be on any company's own pages. This also covers the API.
    host_permissions: ['http://*/*', 'https://*/*'],
    action: { default_title: 'Rolesetu' },
    ...(browser === 'firefox' && {
      browser_specific_settings: {
        gecko: {
          // Permanent once the add-on is listed.
          id: 'extension@rolesetu.vercel.app',
          // The first version that shows the data declaration below at install.
          strict_min_version: '140.0',
          // What leaves the browser: the job listing's text and address, and the
          // fact that the user applied. Must match the privacy policy.
          data_collection_permissions: {
            required: ['websiteContent', 'browsingActivity', 'websiteActivity'],
          },
        },
      },
    }),
  }),
  // Mozilla's reviewers rebuild the add-on from the sources zip, which needs
  // the live addresses. Hidden files are left out unless named.
  zip: { includeSources: ['**', '.env.live'] },
});
