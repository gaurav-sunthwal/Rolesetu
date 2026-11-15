import { describe, expect, it } from 'vitest';

import type { ActivityYear } from '../lib/messages';
import { buildGrid, streakNote } from '../entrypoints/popup/grid';

type Day = ActivityYear['days'][number];

/** `count` days ending on `last` (YYYY-MM-DD), every day with the given activity. */
function daysUntil(last: string, count: number, at: (i: number) => Partial<Day> = () => ({})): Day[] {
  const end = new Date(`${last}T12:00:00Z`).getTime();
  return Array.from({ length: count }, (_, i) => ({
    date: new Date(end - (count - 1 - i) * 86_400_000).toISOString().slice(0, 10),
    applications: 0,
    job_checks: 0,
    extension: 0,
    ai: 0,
    ...at(i),
  }));
}

function year(days: Day[], current: number, longest: number): ActivityYear {
  const last = days.at(-1)!;
  return {
    start: days[0]!.date,
    end: last.date,
    timezone: 'Asia/Kolkata',
    days,
    totals: { ...last, applications: 0, job_checks: 0 },
    streaks: { current, longest, active_days: current },
  };
}

describe('the popup activity grid', () => {
  it('starts on a Sunday and ends today, in the last column', () => {
    // 2026-11-14 is a Saturday: the last column is a full week.
    const grid = buildGrid(daysUntil('2026-11-14', 371));
    expect(grid.cells).toHaveLength(20 * 7);
    expect(grid.cells[0]).toMatchObject({ date: '2026-06-28', column: 0, row: 0 });
    expect(grid.cells.at(-1)).toMatchObject({ date: '2026-11-14', column: 19, row: 6, today: true });
  });

  it('shows this week only up to today', () => {
    // 2026-11-17 is a Tuesday: 19 weeks plus Sunday to Tuesday.
    const grid = buildGrid(daysUntil('2026-11-17', 371));
    expect(grid.cells).toHaveLength(19 * 7 + 3);
    expect(grid.cells.at(-1)).toMatchObject({ column: 19, row: 2 });
  });

  it('shades by jobs applied plus checked, the busiest day darkest', () => {
    const days = daysUntil('2026-11-14', 140, (i) => (i === 139 ? { applications: 4, job_checks: 4 } : i === 0 ? { job_checks: 1 } : {}));
    const grid = buildGrid(days);
    expect(grid.cells.at(-1)?.level).toBe(4);
    expect(grid.cells[0]?.level).toBe(1);
    expect(grid.cells[1]?.level).toBe(0);
    expect(grid).toMatchObject({ applied: 4, checked: 5 });
  });

  it('copes with a new account that has few days', () => {
    const grid = buildGrid(daysUntil('2026-11-14', 3));
    expect(grid.cells).toHaveLength(3);
    expect(grid.cells[0]).toMatchObject({ column: 0, row: 4 });
    expect(buildGrid([]).cells).toHaveLength(0);
  });
});

describe('the streak line', () => {
  it('nudges to start, keep or celebrate a streak', () => {
    const idleToday = daysUntil('2026-11-14', 5);
    const activeToday = daysUntil('2026-11-14', 5, (i) => (i === 4 ? { applications: 1 } : {}));
    expect(streakNote(year(idleToday, 0, 3))).toBe('Check one job today to start a streak');
    expect(streakNote(year(idleToday, 3, 5))).toBe('Keep your 3-day streak: check a job today');
    expect(streakNote(year(activeToday, 4, 4))).toBe('4 days in a row, your best yet');
    expect(streakNote(year(activeToday, 2, 6))).toBe('2 days in a row. Nice!');
  });
});
