/**
 * Fire-and-forget usage analytics for the extension.
 *
 * Usage:
 *   track('autofill_filled', { host: 'capgemini.com', count: 7 });
 *
 * Events are queued in memory and flushed in a single batch either when
 * the queue reaches 10 events, or after 5 seconds of inactivity — whichever
 * comes first. The background worker sends them to /extension/events.
 *
 * Failures are silently dropped: analytics must never disrupt the user.
 * The extension never sends page content, URLs, or personal data — only
 * the hostname (stripped of path) and a numeric count.
 */

import { ask } from './messages';

export type EventName =
  | 'autofill_offered'
  | 'autofill_filled'
  | 'autofill_failed'
  | 'autofill_learned'
  | 'job_scored'
  | 'panel_opened'
  | 'apply_clicked';

export type TrackPayload = {
  /** Hostname only — path is never sent. */
  host?: string;
  /** A small number: fields found/filled, match score, learned count, etc. */
  count?: number;
};

type QueuedEvent = { name: EventName; host?: string; count?: number };

const MAX_BATCH = 10;
const FLUSH_AFTER_MS = 5_000;

const queue: QueuedEvent[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;

function flush(): void {
  clearTimeout(timer);
  if (queue.length === 0) return;
  const batch = queue.splice(0, queue.length);
  // Fire-and-forget: don't await, don't surface errors to the caller.
  void ask({ type: 'track-events', events: batch }).catch(() => undefined);
}

/**
 * Records one extension usage event.
 * Safe to call from any content script context — goes through the background worker.
 */
export function track(name: EventName, payload: TrackPayload = {}): void {
  const host = payload.host ?? safeHostname();
  queue.push({ name, ...(host ? { host } : {}), ...(payload.count !== undefined ? { count: payload.count } : {}) });
  clearTimeout(timer);
  if (queue.length >= MAX_BATCH) {
    flush();
  } else {
    timer = setTimeout(flush, FLUSH_AFTER_MS);
  }
}

/** Returns the current page hostname, stripping www. Never throws. */
function safeHostname(): string | undefined {
  try {
    return window.location.hostname.replace(/^www\./, '') || undefined;
  } catch {
    return undefined;
  }
}
