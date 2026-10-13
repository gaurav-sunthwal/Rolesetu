import { z } from 'zod';

// Where the extension is installed from. Empty until a store has approved it;
// set after approval and the "Install" button appears.
const url = z.url().optional();
const CHROME = url.parse(process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL || undefined);
const FIREFOX = url.parse(process.env.NEXT_PUBLIC_FIREFOX_EXTENSION_URL || undefined);

/** The store page for this browser, or null when the extension is not listed for it yet. */
export function extensionStoreUrl(userAgent: string): string | null {
  // Edge, Brave and Opera install from the Chrome Web Store too.
  return (/firefox/i.test(userAgent) ? FIREFOX : CHROME) ?? null;
}
