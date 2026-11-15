/**
 * The popup's activity grid: the last few weeks as columns (Sunday at the top),
 * one square per day, shaded by the jobs applied to and checked that day. The
 * same idea as the dashboard's year grid, sized for a 340px popup.
 */

import type { ActivityYear } from '@/lib/messages';

type Day = ActivityYear['days'][number];

export type Cell = {
  date: string;
  column: number;
  row: number;
  level: 0 | 1 | 2 | 3 | 4;
  applied: number;
  checked: number;
  today: boolean;
};

export const WEEKS = 20;

/** "2026-11-14" as that calendar day, without a time zone moving it. */
function asDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
}

function levelOf(value: number, max: number): Cell['level'] {
  if (value <= 0 || max <= 0) return 0;
  return Math.min(4, Math.ceil((value / max) * 4)) as Cell['level'];
}

/** `days` is the API's list: oldest first, every day up to today. */
export function buildGrid(days: Day[], weeks = WEEKS) {
  const last = days.at(-1);
  if (!last) return { weeks, cells: [] as Cell[], applied: 0, checked: 0 };
  // Whole weeks before this one, then this week up to today: the first day shown is a Sunday.
  const shown = days.slice(-((weeks - 1) * 7 + asDate(last.date).getDay() + 1));
  const offset = asDate(shown[0]?.date ?? last.date).getDay();
  const max = Math.max(0, ...shown.map((day) => day.applications + day.job_checks));
  const cells = shown.map((day, index): Cell => {
    const at = index + offset;
    return {
      date: day.date,
      column: Math.floor(at / 7),
      row: at % 7,
      level: levelOf(day.applications + day.job_checks, max),
      applied: day.applications,
      checked: day.job_checks,
      today: day === last,
    };
  });
  return {
    weeks,
    cells,
    applied: shown.reduce((sum, day) => sum + day.applications, 0),
    checked: shown.reduce((sum, day) => sum + day.job_checks, 0),
  };
}

export function dayLabel(iso: string): string {
  return asDate(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
}

/** One line under the grid that nudges the next step. */
export function streakNote(activity: ActivityYear): string {
  const today = activity.days.at(-1);
  const doneToday = today ? today.applications + today.job_checks > 0 : false;
  const { current, longest } = activity.streaks;
  if (current === 0) return 'Check one job today to start a streak';
  if (!doneToday) return `Keep your ${current}-day streak: check a job today`;
  if (current >= longest && current > 1) return `${current} days in a row, your best yet`;
  return `${current} day${current === 1 ? '' : 's'} in a row. Nice!`;
}
