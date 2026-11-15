/**
 * The popup's overview (activity grid, application counts, credits) is kept on
 * this device so the popup opens with numbers at once, even after a browser
 * restart, instead of fetching them every time it is opened.
 *
 * - The saved copy is shown straight away, however old.
 * - It is fetched again only when it is older than FRESH_FOR_MS, or was marked
 *   stale by something that changes it here (a job checked, an application
 *   tracked, AI credits spent), or the time zone changed.
 * - It belongs to one account: disconnecting or connecting another clears it.
 */

import type { Summary } from './messages';

export type SavedSummary = {
  summary: Summary;
  savedAt: number;
  timezone: string;
  /** Something changed these numbers since they were fetched. */
  stale: boolean;
};

export const FRESH_FOR_MS = 5 * 60_000;

export function needsRefresh(saved: SavedSummary | null, timezone: string, now: number): boolean {
  if (saved === null) return true;
  return saved.stale || saved.timezone !== timezone || now - saved.savedAt >= FRESH_FOR_MS;
}
