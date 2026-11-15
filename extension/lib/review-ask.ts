/**
 * When to ask for a store review. Ratings decide where Rolesetu shows in the
 * Chrome Web Store search, but a request too early (before the extension has
 * helped) or too often annoys people and earns low stars. So the ask waits until
 * Rolesetu has clearly been useful, over more than one day:
 *
 * - installed (first used) at least 2 days ago, and used on 2 different days;
 * - 5 applications filled or tracked, or 10 jobs scored;
 * - at most 2 asks ever, 21 days apart; never again after a review or "Don't ask again".
 *
 * Counted on this device only (`reviewState` in storage.ts), from the same events
 * the panel already reports, and counted even when usage sharing is off.
 *
 * Everyone is offered the store link first: Chrome Web Store policy does not allow
 * sending only happy users to rate. "Could be better" opens a note to the founder.
 */

import type { TrackedEvent } from './analytics';

export type ReviewState = {
  /** The first day anything was counted: an install that predates this feature starts here. */
  firstSeenAt: number | null;
  scored: number;
  filled: number;
  applied: number;
  /** Local dates (YYYY-MM-DD) with activity, oldest first, the last few only. */
  days: string[];
  askedAt: number | null;
  asks: number;
  done: 'reviewed' | 'never' | null;
};

export type ReviewAnswer = 'review' | 'feedback' | 'later' | 'never';

export const FRESH_REVIEW_STATE: ReviewState = {
  firstSeenAt: null,
  scored: 0,
  filled: 0,
  applied: 0,
  days: [],
  askedAt: null,
  asks: 0,
  done: null,
};

const DAY_MS = 86_400_000;
export const REVIEW_RULES = {
  minAgeDays: 2,
  minActiveDays: 2,
  minApplications: 5,
  minScored: 10,
  maxAsks: 2,
  againAfterDays: 21,
} as const;
const DAYS_KEPT = 10;

/** The Chrome Web Store listing (Edge installs from it too). */
const CHROME_STORE_ID = 'bbpdnhlpapbkiadfdnkhacamojlkfbjl';
export const CHROME_REVIEW_URL = `https://chromewebstore.google.com/detail/${CHROME_STORE_ID}/reviews`;
export const FEEDBACK_MAIL =
  'mailto:gauravsunthwalwork@gmail.com?subject=' + encodeURIComponent('Rolesetu could be better');

function localDay(now: number): string {
  const d = new Date(now);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Applications counted once: autofilling a form and then tracking it is one application. */
export function applications(state: ReviewState): number {
  return Math.max(state.filled, state.applied);
}

/** Adds what these events show the user did. Returns the same object when nothing counts. */
export function countEvents(state: ReviewState, events: TrackedEvent[], now: number): ReviewState {
  let scored = 0;
  let filled = 0;
  let applied = 0;
  for (const event of events) {
    if (event.name === 'job_scored') scored += 1;
    else if (event.name === 'autofill_filled') filled += 1;
    else if (event.name === 'application_tracked' && event.props?.status === 'applied') applied += 1;
  }
  if (scored + filled + applied === 0) return state;
  const today = localDay(now);
  const days = state.days.includes(today) ? state.days : [...state.days, today].slice(-DAYS_KEPT);
  return {
    ...state,
    firstSeenAt: state.firstSeenAt ?? now,
    scored: state.scored + scored,
    filled: state.filled + filled,
    applied: state.applied + applied,
    days,
  };
}

/** Whether to show the ask now. */
export function shouldAsk(state: ReviewState, now: number): boolean {
  const rules = REVIEW_RULES;
  if (state.done !== null || state.firstSeenAt === null) return false;
  if (state.asks >= rules.maxAsks) return false;
  if (state.askedAt !== null && now - state.askedAt < rules.againAfterDays * DAY_MS) return false;
  if (now - state.firstSeenAt < rules.minAgeDays * DAY_MS) return false;
  if (state.days.length < rules.minActiveDays) return false;
  return applications(state) >= rules.minApplications || state.scored >= rules.minScored;
}

/** Shown once counts as an ask, even if the user just closes the panel. */
export function markAsked(state: ReviewState, now: number): ReviewState {
  return { ...state, asks: state.asks + 1, askedAt: now };
}

export function markAnswered(state: ReviewState, answer: ReviewAnswer): ReviewState {
  if (answer === 'review') return { ...state, done: 'reviewed' };
  if (answer === 'never') return { ...state, done: 'never' };
  // "Later" and "Could be better" leave the second ask, 21 days on.
  return state;
}
