'use client';

import { useQuery } from '@tanstack/react-query';
import { Flame } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { api, errorMessage } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { cn } from '@/lib/utils';

type ActivityYear = components['schemas']['ActivityYear'];

// Empty, then four steps of the brand colour, strong enough to read in dark mode.
const LEVELS = [
  'bg-foreground/[0.07]',
  'bg-primary/35',
  'bg-primary/60',
  'bg-primary/85',
  'bg-primary',
] as const;
// About half the widest tooltip, to keep it inside the window.
const TOOLTIP_HALF_WIDTH = 100;
const DAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', ''];
const MONTH = new Intl.DateTimeFormat('en-IN', { month: 'short' });
const LONG_DAY = new Intl.DateTimeFormat('en-IN', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

/** "2026-11-14" as that calendar day, without a time zone shifting it. */
function asDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
}

function levelOf(value: number, max: number): number {
  if (value <= 0 || max <= 0) return 0;
  return Math.min(4, Math.ceil((value / max) * 4));
}

const jobs = (count: number) => `${count} ${count === 1 ? 'job' : 'jobs'}`;

async function getActivity(): Promise<ActivityYear> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const { data } = await api.get<ActivityYear>('/activity/me', { params: { tz } });
  return data;
}

/** Jobs applied to each day over the last year: one square per day, like GitHub's. */
export function ActivityHeatmap() {
  const activity = useQuery({ queryKey: ['activity', 'year'], queryFn: getActivity });

  return (
    <section aria-labelledby="activity-title" className="bg-card rounded-2xl border p-5 sm:p-6">
      {activity.isPending ? (
        <div className="flex flex-col gap-5" aria-hidden>
          <div className="bg-muted h-12 w-72 animate-pulse rounded-lg motion-reduce:animate-none" />
          <div className="bg-muted h-40 animate-pulse rounded-xl motion-reduce:animate-none" />
        </div>
      ) : activity.isError ? (
        <>
          <h3 id="activity-title" className="text-lg font-medium tracking-tight">
            Jobs applied this year
          </h3>
          <p role="alert" className="text-destructive mt-3 text-sm">
            {errorMessage(activity.error)}{' '}
            <button
              type="button"
              className="font-medium underline"
              onClick={() => activity.refetch()}
            >
              Try again
            </button>
          </p>
        </>
      ) : (
        <Year data={activity.data} />
      )}
    </section>
  );
}

function Year({ data }: { data: ActivityYear }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{
    applied: number;
    checked: number;
    date: string;
    left: number;
    top: number;
  } | null>(null);

  const { cells, weeks, months, max } = useMemo(() => {
    const lead = asDate(data.start).getDay(); // weeks start on Sunday
    const placed = data.days.map((day, index) => ({
      day,
      column: Math.floor((index + lead) / 7) + 2, // column 1 holds the day names
      row: ((index + lead) % 7) + 2, // row 1 holds the month names
    }));
    const columnCount = Math.ceil((data.days.length + lead) / 7);
    // A week is labelled with its month when it is the first week starting in it,
    // as on GitHub. A label too close to the next one (a part week) is left out.
    const labels: { column: number; label: string }[] = [];
    let lastMonth = -1;
    for (const cell of placed) {
      if (cell.row !== 2 && cell.column !== 2) continue; // first day of each week
      const date = asDate(cell.day.date);
      if (date.getMonth() === lastMonth) continue;
      lastMonth = date.getMonth();
      const previous = labels[labels.length - 1];
      if (previous && cell.column - previous.column < 3) labels.pop();
      labels.push({ column: cell.column, label: MONTH.format(date) });
    }
    return {
      cells: placed,
      weeks: columnCount,
      months: labels,
      max: Math.max(0, ...data.days.map((day) => day.applications)),
    };
  }, [data]);

  // The tooltip sits on the screen: any scroll would leave it behind, so it goes.
  useEffect(() => {
    if (!hover) return;
    const hide = () => setHover(null);
    window.addEventListener('scroll', hide, { passive: true, capture: true });
    return () => window.removeEventListener('scroll', hide, { capture: true });
  }, [hover]);

  // On narrow screens, start at the most recent weeks.
  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollLeft = element.scrollWidth;
  }, [weeks]);

  const total = data.totals.applications;
  const { current, longest } = data.streaks;
  const today = data.end;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-4">
        <div>
          <h3 id="activity-title" className="text-muted-foreground text-sm font-medium">
            Your job hunt this year
          </h3>
          <dl className="mt-1 flex items-end gap-8">
            <div className="flex flex-col-reverse">
              <dt className="text-muted-foreground mt-1 flex items-center gap-1.5 text-sm">
                <span className="bg-primary size-2.5 rounded-full" aria-hidden />
                Applied
              </dt>
              <dd className="text-4xl font-semibold tracking-[-0.03em] tabular-nums">
                {total.toLocaleString()}
              </dd>
            </div>
            <div className="flex flex-col-reverse">
              <dt className="text-muted-foreground mt-1 text-sm">Checked</dt>
              <dd className="text-4xl font-semibold tracking-[-0.03em] tabular-nums">
                {data.totals.job_checks.toLocaleString()}
              </dd>
            </div>
          </dl>
        </div>
        <dl className="flex gap-8">
          <div>
            <dt className="text-muted-foreground text-sm">Current streak</dt>
            <dd className="mt-1 flex items-center gap-1.5 text-2xl font-semibold tabular-nums">
              <Flame
                className={cn(
                  'size-5',
                  current > 0 ? 'text-orange-500' : 'text-muted-foreground/50',
                )}
                aria-hidden
              />
              {current} {current === 1 ? 'day' : 'days'}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-sm">Best streak</dt>
            <dd className="mt-1 text-2xl font-semibold tabular-nums">
              {longest} {longest === 1 ? 'day' : 'days'}
            </dd>
          </div>
        </dl>
      </div>

      <figure className="mt-6">
        <figcaption className="sr-only">
          {jobs(total)} applied in the last year. Current streak {current} days, best {longest}.
        </figcaption>
        <div
          ref={scroller}
          className="relative overflow-x-auto pb-1"
          onMouseLeave={() => setHover(null)}
        >
          <div
            aria-hidden
            className="grid min-w-[760px] gap-[4px]"
            style={{
              gridTemplateColumns: `2rem repeat(${weeks}, minmax(0, 1fr))`,
              gridTemplateRows: `auto repeat(7, auto)`,
            }}
          >
            {months.map((month) => (
              <span
                key={`${month.column}-${month.label}`}
                className="text-muted-foreground pb-1 text-xs whitespace-nowrap"
                style={{ gridColumn: `${month.column} / span 3`, gridRow: 1 }}
              >
                {month.label}
              </span>
            ))}
            {DAY_LABELS.map((label, index) =>
              label ? (
                <span
                  key={label}
                  className="text-muted-foreground self-center text-xs"
                  style={{ gridColumn: 1, gridRow: index + 2 }}
                >
                  {label}
                </span>
              ) : null,
            )}
            {cells.map(({ day, column, row }) => (
              <span
                key={day.date}
                style={{ gridColumn: column, gridRow: row }}
                onMouseEnter={(event) => {
                  // Placed on the screen, not in the scrolling grid, so it is never
                  // cut off; kept clear of the window's edges.
                  const box = event.currentTarget.getBoundingClientRect();
                  const half = TOOLTIP_HALF_WIDTH;
                  setHover({
                    applied: day.applications,
                    checked: day.job_checks,
                    date: day.date,
                    left: Math.min(
                      Math.max(box.left + box.width / 2, half + 8),
                      window.innerWidth - half - 8,
                    ),
                    top: box.top,
                  });
                }}
                className={cn(
                  'hover:ring-foreground/40 aspect-square rounded-[4px] hover:ring-2 hover:ring-inset',
                  LEVELS[levelOf(day.applications, max)],
                  day.date === today && 'ring-foreground/70 ring-2 ring-inset',
                )}
              />
            ))}
          </div>
          {hover ? (
            <span
              role="tooltip"
              className="bg-foreground text-background pointer-events-none fixed z-50 flex -translate-x-1/2 -translate-y-full flex-col items-center rounded-lg px-3 py-1.5 text-center whitespace-nowrap shadow-lg"
              style={{ left: hover.left, top: hover.top - 8 }}
            >
              <span className="text-xs opacity-70">{LONG_DAY.format(asDate(hover.date))}</span>
              <span className="mt-1 flex gap-3 text-sm">
                <span>
                  <strong className="font-semibold tabular-nums">{hover.applied}</strong> applied
                </span>
                <span>
                  <strong className="font-semibold tabular-nums">{hover.checked}</strong> checked
                </span>
              </span>
            </span>
          ) : null}
        </div>

        <div className="text-muted-foreground mt-4 flex flex-wrap items-center justify-between gap-3 text-xs">
          <span>
            {total === 0
              ? 'No applications yet. Every job you apply to fills in a day.'
              : 'Hover a day to see how many jobs you applied to and checked.'}
          </span>
          <span className="flex items-center gap-1.5" aria-hidden>
            Less
            {LEVELS.map((level) => (
              <span key={level} className={cn('size-3.5 rounded-[4px]', level)} />
            ))}
            More
          </span>
        </div>
      </figure>
    </>
  );
}
