/**
 * Usage analytics for the extension: what people do with it, never what they
 * write. An event is a name, the site's hostname, a small number and a few short
 * labels (`props`): no page content, no URLs, no typed text, no answers.
 *
 *   track('autofill_filled', { count: 7, props: { drafts: 2 } });
 *
 * Events go to the background worker, which stamps them (version, session) and
 * keeps them in a queue that survives the worker sleeping and the browser not
 * being connected yet (see `analytics-queue.ts`). The user can switch it off in
 * the popup. Failures are dropped: analytics must never get in the user's way.
 */

import { ask } from './messages';

export type EventName =
  | 'extension_installed'
  | 'extension_updated'
  | 'extension_connected'
  | 'setup_opened'
  | 'popup_opened'
  | 'page_checked'
  | 'job_detected'
  | 'form_detected'
  | 'panel_opened'
  | 'job_scored'
  | 'apply_clicked'
  | 'application_tracked'
  | 'autofill_offered'
  | 'autofill_filled'
  | 'autofill_failed'
  | 'autofill_undone'
  | 'autofill_learned'
  | 'answer_saved'
  | 'suggestion_shown'
  | 'suggestion_used'
  | 'ai_requested'
  | 'ai_succeeded'
  | 'ai_failed'
  | 'ext_error';

/** Short labels only: a source, a mode, a reason. Never anything the user wrote. */
export type Props = Record<string, string | number | boolean>;

export type TrackPayload = {
  /** Hostname only: the path is never sent. Defaults to this page's. */
  host?: string;
  /** A small number: fields filled, match score, etc. */
  count?: number;
  props?: Props;
};

/** One event as it travels to the background worker. */
export type TrackedEvent = {
  name: EventName;
  id: string;
  at: string;
  host?: string;
  count?: number;
  props?: Props;
};

const FLUSH_AFTER_MS = 2_000;
const MAX_BATCH = 20;

const queue: TrackedEvent[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;

function flush(): void {
  clearTimeout(timer);
  if (queue.length === 0) return;
  const batch = queue.splice(0, queue.length);
  void ask({ type: 'track-events', events: batch }).catch(() => undefined);
}

/** Builds an event with its own id and time, ready to queue. */
export function newEvent(name: EventName, payload: TrackPayload = {}, host = pageHost()): TrackedEvent {
  const event: TrackedEvent = { name, id: crypto.randomUUID(), at: new Date().toISOString() };
  const where = payload.host ?? host;
  if (where) event.host = where.slice(0, 120);
  if (payload.count !== undefined) event.count = Math.max(0, Math.min(100_000, Math.round(payload.count)));
  if (payload.props) event.props = payload.props;
  return event;
}

/** Records one event. Safe anywhere in a page or the popup; never throws. */
export function track(name: EventName, payload: TrackPayload = {}): void {
  try {
    queue.push(newEvent(name, payload));
  } catch {
    return;
  }
  clearTimeout(timer);
  if (queue.length >= MAX_BATCH) flush();
  else timer = setTimeout(flush, FLUSH_AFTER_MS);
}

const once = new Set<string>();

/**
 * Records an event once per `key` on this page: the autofill offer is worked out
 * again every time the page changes, but it was offered once.
 */
export function trackOnce(key: string, name: EventName, payload: TrackPayload = {}): void {
  const scoped = `${globalThis.location?.href ?? ''}|${name}|${key}`;
  if (once.has(scoped)) return;
  once.add(scoped);
  track(name, payload);
}

let errorsSent = 0;
const MAX_ERRORS_PER_PAGE = 5;

/**
 * Reports this extension's own failures (not the page's): which part failed and
 * the error's kind ("TypeError"), never its message, which may hold page text.
 */
export function watchErrors(
  where: string,
  target: EventTarget,
  report: (name: EventName, payload: TrackPayload) => void = track,
): void {
  const ours = (stack: unknown) =>
    typeof stack === 'string' && stack.includes(browser.runtime.getURL('').replace(/\/$/, ''));
  const onError = (error: unknown) => {
    if (errorsSent >= MAX_ERRORS_PER_PAGE) return;
    const stack = error instanceof Error ? error.stack : undefined;
    // In a page, only errors from our own code; in our own pages, all of them.
    if (where === 'content' && !ours(stack)) return;
    errorsSent += 1;
    report('ext_error', { props: { where, kind: error instanceof Error ? error.name : 'unknown' } });
  };
  target.addEventListener('error', (event: Event) => onError((event as ErrorEvent).error));
  target.addEventListener('unhandledrejection', (event: Event) => onError((event as PromiseRejectionEvent).reason));
}

/** This page's hostname without "www.", only on a website (not the extension's own pages). Never throws. */
function pageHost(): string | undefined {
  try {
    const { protocol, hostname } = globalThis.location;
    if (protocol !== 'http:' && protocol !== 'https:') return undefined;
    return hostname.replace(/^www\./, '') || undefined;
  } catch {
    return undefined;
  }
}
