/**
 * Reports how far a new extension install got in setting up: the page loaded,
 * sign-up started, sign-in failed (and why), signed in, connecting failed.
 *
 * Only for a browser the extension sent here: its link carries the install's
 * random id (`?install=`), or the extension says it when asked. Without one,
 * nothing is sent. Short labels only: never an email, a name or anything typed.
 */

import { z } from 'zod';

const STORED = 'rolesetu.install';
const installIdSchema = z.uuid();
const API = (process.env.NEXT_PUBLIC_API_BASE_URL ?? '').replace(/\/$/, '');

export type SetupStep =
  | 'setup_page_seen'
  | 'signup_started'
  | 'sign_in_failed'
  | 'signed_in'
  | 'connect_failed'
  | 'uninstall_reason';

function read(): string | null {
  try {
    return window.localStorage.getItem(STORED);
  } catch {
    return null;
  }
}

/** Keeps the install id from this page's link, or one the extension gave. */
export function rememberInstall(id: string | null | undefined): string | null {
  const parsed = installIdSchema.safeParse(id);
  if (!parsed.success) return read();
  try {
    window.localStorage.setItem(STORED, parsed.data);
  } catch {
    // Storage blocked: this page can still report with the id from its link.
  }
  return parsed.data;
}

/** The install id from this page's link, else the one kept earlier. */
export function installFromPage(): string | null {
  return rememberInstall(new URLSearchParams(window.location.search).get('install'));
}

/** Records one setup step for this install. Never throws, never waits on the reply. */
export function trackSetup(
  name: SetupStep,
  props: Record<string, string | number | boolean> = {},
  install: string | null = installFromPage(),
): void {
  if (!install || !API) return;
  const body = {
    install: { id: install, automated: navigator.webdriver === true },
    events: [{ name, id: crypto.randomUUID(), at: new Date().toISOString(), props }],
  };
  try {
    void fetch(`${API}/api/v1/extension/installs/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      // Sent even when the page is navigating away (sign-in redirects at once).
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // Reporting must never get in the way of signing up.
  }
}
