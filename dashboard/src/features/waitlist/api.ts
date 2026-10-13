import { api } from '@/lib/api/client';
import type { WaitlistJoin } from '@/lib/api/types';

/** Asks to be emailed when the browser extension is released. Works without signing in. */
export async function joinExtensionWaitlist(body: WaitlistJoin): Promise<void> {
  await api.post('/public/extension-waitlist', body);
}
