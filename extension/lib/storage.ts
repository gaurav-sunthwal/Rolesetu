import { storage } from '#imports';

import { FRESH_REVIEW_STATE, type ReviewState } from './review-ask';
import type { SavedSummary } from './summary-cache';

/** The key the dashboard issued for this browser. Kept on this device only. */
export const accessKey = storage.defineItem<string | null>('local:accessKey', { fallback: null });

/** The user switched usage analytics off in the popup. */
export const analyticsOff = storage.defineItem<boolean>('local:analyticsOff', { fallback: false });

/**
 * A random id this install made for itself, so the steps from install to sign-in
 * can be followed (and the uninstall counted) without knowing who anyone is.
 */
export const installId = storage.defineItem<string | null>('local:installId', { fallback: null });

/** What counts toward asking for a store review (see review-ask.ts). This device only. */
export const reviewState = storage.defineItem<ReviewState>('local:reviewAsk', {
  fallback: FRESH_REVIEW_STATE,
});

/** The popup's last overview, shown at once when it opens (see summary-cache.ts). */
export const savedSummary = storage.defineItem<SavedSummary | null>('local:summaryCache', { fallback: null });
