const KEY = 'rolesetu.pending-job';

/**
 * The job link a visitor looked up on the landing page, kept while they sign
 * in (and build a profile, if they are new) so the check page can score it.
 * Browsers can refuse storage, so every call tolerates that.
 */
export function savePendingJob(url: string): void {
  try {
    window.sessionStorage.setItem(KEY, url);
  } catch {
    // Without storage the visitor simply pastes the link again after signing in.
  }
}

export function readPendingJob(): string | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function clearPendingJob(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // Nothing was stored.
  }
}
