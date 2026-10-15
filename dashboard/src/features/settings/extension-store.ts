import { z } from 'zod';

import { SITE } from '@/lib/site';

// Firefox has no listing yet: set this once one is approved and its "Install" button appears.
const FIREFOX = z
  .url()
  .optional()
  .parse(process.env.NEXT_PUBLIC_FIREFOX_EXTENSION_URL || undefined);

/** The store page for this browser, or null when the extension is not listed for it yet. */
export function extensionStoreUrl(userAgent: string): string | null {
  // Edge, Brave and Opera install from the Chrome Web Store too.
  return (/firefox/i.test(userAgent) ? FIREFOX : SITE.chromeExtensionUrl) ?? null;
}
