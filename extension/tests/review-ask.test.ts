import { describe, expect, it } from 'vitest';

import type { TrackedEvent } from '../lib/analytics';
import {
  applications,
  countEvents,
  FRESH_REVIEW_STATE,
  markAnswered,
  markAsked,
  type ReviewState,
  shouldAsk,
} from '../lib/review-ask';

const DAY = 86_400_000;
const START = new Date(2026, 10, 10, 10).getTime();

function event(name: TrackedEvent['name'], props?: TrackedEvent['props']): TrackedEvent {
  return { name, id: crypto.randomUUID(), at: new Date(START).toISOString(), ...(props && { props }) };
}

const filled = () => event('autofill_filled');

/** A user who filled `n` forms on the first day and came back two days later. */
function used(n: number): ReviewState {
  let state = countEvents(FRESH_REVIEW_STATE, Array.from({ length: n }, filled), START);
  state = countEvents(state, [event('job_scored')], START + 2 * DAY);
  return state;
}

describe('counting what Rolesetu helped with', () => {
  it('counts scores, fills and applications, and the days they happened on', () => {
    const state = countEvents(
      FRESH_REVIEW_STATE,
      [event('job_scored'), filled(), event('application_tracked', { status: 'applied' })],
      START,
    );
    expect(state).toMatchObject({ scored: 1, filled: 1, applied: 1, firstSeenAt: START });
    expect(state.days).toHaveLength(1);
  });

  it('ignores saved jobs and unrelated events, returning the same state', () => {
    const events = [event('application_tracked', { status: 'saved' }), event('popup_opened')];
    expect(countEvents(FRESH_REVIEW_STATE, events, START)).toBe(FRESH_REVIEW_STATE);
  });

  it('does not count one application twice when it was filled and then tracked', () => {
    const state = countEvents(
      FRESH_REVIEW_STATE,
      [filled(), event('application_tracked', { status: 'applied' })],
      START,
    );
    expect(applications(state)).toBe(1);
  });

  it('keeps each day once and only the last ten', () => {
    let state = FRESH_REVIEW_STATE;
    for (let d = 0; d < 12; d += 1) {
      state = countEvents(state, [filled(), filled()], START + d * DAY);
    }
    expect(state.days).toHaveLength(10);
    expect(new Set(state.days).size).toBe(10);
  });
});

describe('when to ask for a review', () => {
  it('asks after 5 applications over two days, once 2 days have passed', () => {
    expect(shouldAsk(used(5), START + 2 * DAY)).toBe(true);
  });

  it('waits for enough use', () => {
    expect(shouldAsk(used(3), START + 2 * DAY)).toBe(false);
  });

  it('waits for a second day of use, however much happened on the first', () => {
    const oneBusyDay = countEvents(FRESH_REVIEW_STATE, Array.from({ length: 20 }, filled), START);
    expect(shouldAsk(oneBusyDay, START + 5 * DAY)).toBe(false);
  });

  it('also asks after 10 scored jobs', () => {
    let state = countEvents(FRESH_REVIEW_STATE, Array.from({ length: 9 }, () => event('job_scored')), START);
    state = countEvents(state, [event('job_scored')], START + 3 * DAY);
    expect(shouldAsk(state, START + 3 * DAY)).toBe(true);
  });

  it('asks a second time only 21 days later, and never a third', () => {
    const now = START + 2 * DAY;
    const once = markAsked(used(5), now);
    expect(shouldAsk(once, now + 20 * DAY)).toBe(false);
    expect(shouldAsk(once, now + 21 * DAY)).toBe(true);
    const twice = markAsked(once, now + 21 * DAY);
    expect(shouldAsk(twice, now + 100 * DAY)).toBe(false);
  });

  it('stops for good after a review or "Don\'t ask again"', () => {
    const now = START + 2 * DAY;
    expect(shouldAsk(markAnswered(used(5), 'review'), now)).toBe(false);
    expect(shouldAsk(markAnswered(used(5), 'never'), now)).toBe(false);
    expect(markAnswered(used(5), 'later')).toEqual(used(5));
  });
});
