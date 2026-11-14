/**
 * The background worker's side of analytics: stamps each event with the
 * extension's version and browser session, keeps them in storage (the worker is
 * stopped whenever it is idle, and events from before the browser is connected
 * must wait), and sends them in batches once there is an account to send them to.
 */

import { storage } from '#imports';

import { type EventName, newEvent, type TrackedEvent, type TrackPayload } from './analytics';
import { analyticsOff } from './storage';

type StoredEvent = TrackedEvent & { version: string; session: string };

const MAX_KEPT = 300;
const BATCH = 50;
const SEND_AFTER_MS = 4_000;

const kept = storage.defineItem<StoredEvent[]>('local:analyticsQueue', { fallback: [] });
const browserSession = storage.defineItem<string | null>('session:analyticsSession', { fallback: null });

/** Sends one batch; resolves to the server's answer: sent, rejected for good, or try later. */
export type Send = (events: StoredEvent[]) => Promise<'sent' | 'rejected' | 'later'>;

let send: Send | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
// Storage is read, changed and written back: one change at a time.
let busy: Promise<unknown> = Promise.resolve();
const serially = <T>(work: () => Promise<T>): Promise<T> => {
  const next = busy.then(work, work);
  busy = next.catch(() => undefined);
  return next;
};

async function sessionId(): Promise<string> {
  const current = await browserSession.getValue();
  if (current) return current;
  const created = crypto.randomUUID();
  await browserSession.setValue(created);
  return created;
}

/** Keeps events to send. Nothing is kept while the user has analytics switched off. */
export function enqueue(events: TrackedEvent[]): Promise<void> {
  return serially(async () => {
    if (events.length === 0 || (await analyticsOff.getValue())) return;
    const version = browser.runtime.getManifest().version;
    const session = await sessionId();
    const stamped = events.map((event) => ({ ...event, version, session }));
    await kept.setValue([...(await kept.getValue()), ...stamped].slice(-MAX_KEPT));
    schedule();
  });
}

/** Records an event that happens in the background worker itself (install, connect...). */
export function record(name: EventName, payload: TrackPayload = {}, host?: string): void {
  void enqueue([newEvent(name, payload, host)]).catch(() => undefined);
}

function schedule(delay = SEND_AFTER_MS): void {
  clearTimeout(timer);
  timer = setTimeout(() => void flush(), delay);
}

/** Sends what is kept, a batch at a time, until done or the server says later. */
export function flush(): Promise<void> {
  return serially(async () => {
    if (send === null) return;
    for (;;) {
      const queue = await kept.getValue();
      if (queue.length === 0) return;
      const batch = queue.slice(0, BATCH);
      const outcome = await send(batch).catch(() => 'later' as const);
      if (outcome === 'later') return;
      // Sent, or refused for good (it would be refused every time): either way, done with it.
      const done = new Set(batch.map((event) => event.id));
      await kept.setValue((await kept.getValue()).filter((event) => !done.has(event.id)));
    }
  });
}

/** Starts sending, with the function that talks to the API. */
export function startAnalytics(sender: Send): void {
  send = sender;
  schedule(1_000);
}
