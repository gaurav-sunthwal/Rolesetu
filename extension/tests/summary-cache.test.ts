import { describe, expect, it } from 'vitest';

import type { Summary } from '../lib/messages';
import { FRESH_FOR_MS, needsRefresh, type SavedSummary } from '../lib/summary-cache';

const NOW = Date.UTC(2026, 10, 15, 10);
const summary: Summary = { activity: null, stats: null, credits: null };
const saved = (over: Partial<SavedSummary> = {}): SavedSummary => ({
  summary,
  savedAt: NOW - 60_000,
  timezone: 'Asia/Kolkata',
  stale: false,
  ...over,
});

describe('when the popup fetches its numbers again', () => {
  it('fetches when nothing is saved', () => {
    expect(needsRefresh(null, 'Asia/Kolkata', NOW)).toBe(true);
  });

  it('uses a recent copy without fetching', () => {
    expect(needsRefresh(saved(), 'Asia/Kolkata', NOW)).toBe(false);
  });

  it('fetches once the copy is 5 minutes old', () => {
    expect(needsRefresh(saved({ savedAt: NOW - FRESH_FOR_MS }), 'Asia/Kolkata', NOW)).toBe(true);
  });

  it('fetches after something changed the numbers, or the time zone changed', () => {
    expect(needsRefresh(saved({ stale: true }), 'Asia/Kolkata', NOW)).toBe(true);
    expect(needsRefresh(saved(), 'Europe/London', NOW)).toBe(true);
  });
});
