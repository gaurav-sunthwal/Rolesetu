import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { whenSettled } from '../lib/settled';

describe('whenSettled', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('runs once after the calls stop', () => {
    const task = vi.fn();
    const poke = whenSettled(task, 700, 2000);
    poke();
    vi.advanceTimersByTime(300);
    poke();
    vi.advanceTimersByTime(699);
    expect(task).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(task).toHaveBeenCalledTimes(1);
  });

  it('still runs on a page that never goes quiet', () => {
    const task = vi.fn();
    const poke = whenSettled(task, 700, 2000);
    for (let elapsed = 0; elapsed < 6000; elapsed += 100) {
      poke();
      vi.advanceTimersByTime(100);
    }
    expect(task.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('does nothing once cancelled', () => {
    const task = vi.fn();
    const poke = whenSettled(task, 700, 2000);
    poke();
    poke.cancel();
    vi.advanceTimersByTime(5000);
    expect(task).not.toHaveBeenCalled();
  });
});
