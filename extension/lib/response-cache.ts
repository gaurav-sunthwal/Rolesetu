import { storage } from '#imports';

import type { Result } from './messages';

/**
 * Answers the server already gave, kept for a short while so a page seen again
 * (going back and forth between jobs, a reload, a second form on the same site)
 * is answered at once, without asking the server again.
 *
 * Kept in session storage: in memory only, never written to disk, and gone when
 * the browser closes, so a person's profile is not left behind on the device.
 * Only successful answers are kept. Background worker only (see session-storage.ts).
 */

type Entry = { value: unknown; savedAt: number };

const PREFIX = 'cache:';

export const JOB_FOR_MS = 10 * 60_000;
export const KEYWORDS_FOR_MS = 30 * 60_000;
export const AUTOFILL_FOR_MS = 10 * 60_000;

const keyOf = (name: string) => `session:${PREFIX}${name}` as const;

/** The saved answer for `name` if it is younger than `maxAgeMs`, else a fresh one from `load`. */
export async function cached<T>(
  name: string,
  maxAgeMs: number,
  load: () => Promise<Result<T>>,
): Promise<Result<T>> {
  const saved = await storage.getItem<Entry>(keyOf(name)).catch(() => null);
  if (saved && Date.now() - saved.savedAt < maxAgeMs) return saved.value as Result<T>;

  const fresh = await load();
  if (fresh.ok) {
    await storage
      .setItem<Entry>(keyOf(name), { value: fresh, savedAt: Date.now() })
      .catch(() => undefined);
  }
  return fresh;
}

/** Forgets every saved answer whose name starts with `start` ("" forgets them all). */
export async function forget(start = ''): Promise<void> {
  const all = await storage.snapshot('session').catch(() => ({}));
  const names = Object.keys(all).filter((name) => name.startsWith(`${PREFIX}${start}`));
  if (names.length > 0) {
    await storage
      .removeItems(names.map((name) => `session:${name}` as const))
      .catch(() => undefined);
  }
}

/** A short, stable name for a long piece of text (a job description). */
export async function digest(text: string): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes).slice(0, 16), (byte) =>
    byte.toString(16).padStart(2, '0'),
  ).join('');
}
