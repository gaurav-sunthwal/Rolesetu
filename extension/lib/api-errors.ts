/**
 * Turns whatever the server said (or failed to say) into one sentence the user
 * can act on. Nothing here talks to the network, so all of it can be tested.
 */

export const UNREACHABLE =
  'Could not reach Rolesetu. It may be starting up: wait a few seconds and try again. If it keeps happening, check your connection.';

/** The message to show for a reply that was not a success. */
export function messageFor(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  // The server writes these for people, so they are shown as they are.
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  // An older server lists what was wrong field by field: show the first reason.
  if (Array.isArray(detail)) {
    const first = (detail[0] as { msg?: unknown } | undefined)?.msg;
    if (typeof first === 'string' && first.trim()) return first.replace(/^Value error, /, '');
  }
  if (status === 429) return 'You have done that a lot in a short time. Wait a minute and try again.';
  if (status === 413) return 'That is too large for Rolesetu to handle.';
  if (status === 404) return 'That is no longer there. Refresh the page and try again.';
  if (status === 403) return 'That can only be done from the Rolesetu dashboard.';
  if (status >= 500) {
    return 'Rolesetu had a problem on its side, not yours. Try again in a moment.';
  }
  return 'Rolesetu could not do that with what this page gave it. Refresh the page and try again.';
}

// The limits the server accepts (see MatchCreate in the backend).
export const MIN_DESCRIPTION = 200;
const MAX_DESCRIPTION = 20000;
const MAX_NAME = 160;
const MAX_URL = 2000;

/** A page address short enough to store: without its tracking tail if need be, or not at all. */
export function fitUrl(url: string): string | null {
  if (url.length <= MAX_URL) return url;
  const bare = url.split(/[?#]/)[0] ?? '';
  return bare.length > 0 && bare.length <= MAX_URL ? bare : null;
}

function fitName(value: string | null): string | null {
  const text = value?.replace(/\s+/g, ' ').trim() ?? '';
  return text ? text.slice(0, MAX_NAME).trim() : null;
}

export type JobRequest = {
  jd_text: string;
  url: string | null;
  role: string | null;
  company: string | null;
};

/**
 * What a page gave us, cut to what the server accepts, so a long title or a
 * long address can never make a job check fail. Returns a sentence instead
 * when there is too little to score.
 */
export function fitJob(job: {
  title: string | null;
  company: string | null;
  description: string;
  url: string;
}): JobRequest | { problem: string } {
  const description = job.description.trim().slice(0, MAX_DESCRIPTION).trim();
  if (description.length < MIN_DESCRIPTION) {
    return {
      problem:
        'This page shows too little of the job to score it. Open the full job description and try again.',
    };
  }
  return {
    jd_text: description,
    url: fitUrl(job.url),
    role: fitName(job.title),
    company: fitName(job.company),
  };
}
