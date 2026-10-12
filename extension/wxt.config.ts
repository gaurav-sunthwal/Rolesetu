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
  manifest: {
    name: 'Rolesetu',
    description:
      'See your match score on any job page, fill application forms from your profile, and track the jobs you apply to.',
    permissions: ['storage', 'scripting'],
    // Every site: a job can be on any company's own pages. This also covers the API.
    host_permissions: ['http://*/*', 'https://*/*'],
    action: { default_title: 'Rolesetu' },
  },
});
