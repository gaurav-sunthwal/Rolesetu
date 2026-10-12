export const API_BASE_URL = (
  (import.meta.env.WXT_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'
).replace(/\/$/, '');

export const DASHBOARD_URL = (
  (import.meta.env.WXT_DASHBOARD_URL as string | undefined) ?? 'http://localhost:3000'
).replace(/\/$/, '');

/**
 * Pages allowed to hand the extension its key. Only the local dashboard for
 * now: add the production address here once the dashboard has one.
 */
export const DASHBOARD_MATCHES = ['http://localhost:3000/*'];

/**
 * The page detector runs on every website, because a job can be posted on any
 * company's own site. It is a small script that stays silent unless the page
 * is a job listing or an application form.
 */
export const ALL_SITES = ['http://*/*', 'https://*/*'];
