import { storage } from '#imports';

/** The key the dashboard issued for this browser. Kept on this device only. */
export const accessKey = storage.defineItem<string | null>('local:accessKey', { fallback: null });
