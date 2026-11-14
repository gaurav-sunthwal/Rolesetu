/**
 * What this install is, for following new installs before anyone signs in: a
 * random id, and what the browser says about itself (no address, no name).
 */

import { type Brand, browserName, plain } from './browser-name';
import { installId } from './storage';

export type InstallInfo = {
  id: string;
  version: string;
  browser?: string;
  os?: string;
  arch?: string;
  language?: string;
  timezone?: string;
};

let made: Promise<string> | null = null;

/** This install's id, made on first use and kept until the extension is removed. */
export function ownInstallId(): Promise<string> {
  made ??= installId.getValue().then(async (current) => {
    if (current) return current;
    const created = crypto.randomUUID();
    await installId.setValue(created);
    return created;
  });
  return made;
}

export async function installInfo(): Promise<InstallInfo> {
  const nav = navigator as Navigator & { userAgentData?: { brands?: Brand[] } };
  const platform = await browser.runtime.getPlatformInfo().catch(() => null);
  let timezone: string | undefined;
  try {
    timezone = plain(Intl.DateTimeFormat().resolvedOptions().timeZone, 50, /[^\w/+-]/g);
  } catch {
    timezone = undefined;
  }
  return {
    id: await ownInstallId(),
    version: browser.runtime.getManifest().version,
    browser: browserName(nav.userAgentData?.brands, nav.userAgent),
    os: plain(platform?.os, 20),
    arch: plain(platform?.arch, 20),
    language: plain(nav.language, 20),
    timezone,
  };
}
