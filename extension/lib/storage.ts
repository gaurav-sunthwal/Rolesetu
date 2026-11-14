import { storage } from '#imports';

/** The key the dashboard issued for this browser. Kept on this device only. */
export const accessKey = storage.defineItem<string | null>('local:accessKey', { fallback: null });

/** The user switched usage analytics off in the popup. */
export const analyticsOff = storage.defineItem<boolean>('local:analyticsOff', { fallback: false });

/**
 * A random id this install made for itself, so the steps from install to sign-in
 * can be followed (and the uninstall counted) without knowing who anyone is.
 */
export const installId = storage.defineItem<string | null>('local:installId', { fallback: null });
