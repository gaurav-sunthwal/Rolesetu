/**
 * Per-site profile storage.
 *
 * Every form answer the user picks or types on a given hostname is remembered
 * against that hostname in local (persistent) storage. The next time the user
 * lands on the same site, the saved answers are merged into the autofill data
 * before the form is scanned — so dropdowns and custom questions are already
 * known without a round-trip to the server or any "learning" delay.
 *
 * Structure stored at `local:siteProfile:<hostname>`:
 *   { [question_key: string]: string }
 *
 * This is completely separate from the server-side `saved_answers` dict. Both
 * are merged at fill time: server answers first (the user's canonical choice),
 * site answers as a fallback.  This way:
 *  - A Capgemini-specific answer never leaks to a different site.
 *  - A profile-level answer (e.g. work_authorization = "Yes") is used
 *    everywhere but can be overridden per site.
 */

import { storage } from '#imports';

const PREFIX = 'local:siteProfile:';

/** Stable key for a hostname (strips leading "www."). */
export function siteKey(hostname: string): string {
  return hostname.replace(/^www\./, '').toLowerCase();
}

/** All answers saved for `hostname`. Returns an empty object if none. */
export async function getSiteProfile(hostname: string): Promise<Record<string, string>> {
  const key = `${PREFIX}${siteKey(hostname)}` as const;
  return (await storage.getItem<Record<string, string>>(key).catch(() => null)) ?? {};
}

/**
 * Merges `answers` into the stored profile for `hostname`.
 * Existing keys are updated; new keys are added; nothing is removed.
 */
export async function saveSiteProfile(
  hostname: string,
  answers: Record<string, string>,
): Promise<void> {
  if (Object.keys(answers).length === 0) return;
  const key = `${PREFIX}${siteKey(hostname)}` as const;
  const existing = (await storage.getItem<Record<string, string>>(key).catch(() => null)) ?? {};
  const merged = { ...existing, ...answers };
  await storage.setItem(key, merged).catch(() => undefined);
}

/**
 * Returns a copy of `data.saved_answers` enriched with site-specific answers
 * from local storage.  Server answers always win so the user's canonical
 * choices are never silently overridden.
 */
export function mergeSiteAnswers(
  serverAnswers: Record<string, string>,
  siteAnswers: Record<string, string>,
): Record<string, string> {
  // Site answers fill the gaps; server answers take priority.
  return { ...siteAnswers, ...serverAnswers };
}
