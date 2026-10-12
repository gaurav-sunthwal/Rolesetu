import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  // A visible folder name: macOS hides dot-folders in Chrome's "Load unpacked" picker.
  outDir: 'dist',
  manifest: {
    name: 'Rolesetu',
    description: 'See how well you fit a job, right on the job page.',
    permissions: ['storage', 'scripting'],
    // Every site: a job can be on any company's own pages. This also covers the API.
    host_permissions: ['http://*/*', 'https://*/*'],
    action: { default_title: 'Rolesetu' },
  },
});
