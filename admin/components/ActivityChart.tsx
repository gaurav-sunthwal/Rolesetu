import Link from 'next/link';

import { formatDay } from '@/lib/format';

type Day = { day: string; signups: number; job_checks: number; applications?: number };

// `list` is the page that shows one day of that series.
const SERIES = [
  {
    key: 'signups',
    label: 'Sign-ups',
    color: 'bg-zinc-900',
    list: (day: string) => `/users?joined_on=${day}`,
  },
  {
    key: 'job_checks',
    label: 'Job checks',
    color: 'bg-blue-500',
    list: (day: string) => `/job-checks?day=${day}`,
  },
  {
    key: 'applications',
    label: 'Applications',
    color: 'bg-emerald-500',
    list: (day: string) => `/applications?day=${day}`,
  },
] as const;

/**
 * Bars per day, one per series present in the data. Each bar opens that day's
 * list. With many days only some dates are labelled, so they stay readable.
 */
export function ActivityChart({ days }: { days: Day[] }) {
  const series = SERIES.filter((item) => days.some((day) => day[item.key] !== undefined));
  const top = Math.max(1, ...days.flatMap((day) => series.map((item) => day[item.key] ?? 0)));
  const labelEvery = Math.max(1, Math.ceil(days.length / 14));

  return (
    <div>
      <p className="flex flex-wrap gap-4 text-xs text-zinc-500">
        {series.map((item) => (
          <span key={item.key} className="flex items-center gap-1.5">
            <span className={`size-2.5 rounded-sm ${item.color}`} /> {item.label}
          </span>
        ))}
        <span>Click a bar to see that day.</span>
      </p>
      <div className={`mt-5 flex h-48 items-end ${days.length > 60 ? 'gap-px' : 'gap-1.5'}`}>
        {days.map((day, index) => (
          <div key={day.day} className="flex h-full min-w-0 flex-1 flex-col justify-end gap-1">
            <div className="flex flex-1 items-end gap-0.5">
              {series.map((item) => {
                const value = day[item.key] ?? 0;
                const bar = (
                  <span
                    className={`block w-full rounded-t ${item.color}`}
                    style={{ height: `${(value / top) * 100}%` }}
                  />
                );
                const label = `${formatDay(day.day)}: ${value} ${item.label.toLowerCase()}`;
                // The whole column is the target, so a short bar is as easy to hit as a tall one.
                return value ? (
                  <Link
                    key={item.key}
                    href={item.list(day.day)}
                    title={`${label}. Open the list`}
                    aria-label={`${label}. Open the list`}
                    className="flex h-full flex-1 cursor-pointer items-end rounded-t hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-zinc-900 [&>span]:hover:opacity-80"
                  >
                    {bar}
                  </Link>
                ) : (
                  <span key={item.key} title={label} className="flex h-full flex-1 items-end">
                    {bar}
                  </span>
                );
              })}
            </div>
            <p className="h-3 truncate text-center text-[10px] text-zinc-500" aria-hidden>
              {index % labelEvery === 0 ? formatDay(day.day) : ''}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
