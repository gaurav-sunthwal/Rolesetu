import { storage } from '#imports';

import type { PendingApply } from './messages';

/**
 * The application in progress, if any. Cleared when the browser closes.
 *
 * Kept in its own file because only the background worker may load it: Chrome
 * does not let scripts running inside web pages touch session storage, and
 * merely importing this from one of them raises an error on that page.
 */
export const pendingApply = storage.defineItem<PendingApply | null>('session:pendingApply', {
  fallback: null,
});
