'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Suspense, useState } from 'react';

import { ActivityChart } from '@/components/ActivityChart';
import { Card, Empty, ErrorNote, Loading, PageHeader, pill, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDate } from '@/lib/format';
import type { DailyActivity } from '@/lib/types';
import { useSetUrlFilters, useUrlFilter } from '@/lib/url-filter';

const PRESETS = [7, 14, 30, 90, 365] as const;
const MAX_DAYS = 366;

/** A UTC date as YYYY-MM-DD, the form the API and date inputs use. */
const iso = (day: Date) => day.toISOString().slice(0, 10);
const today = () => iso(new Date());
const daysBefore = (end: string, days: number) => {
  const day = new Date(`${end}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - (days - 1));
  return iso(day);
};
const span = (start: string, end: string) =>
  Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1;

function Activity() {
  const [startParam] = useUrlFilter('start');
  const [endParam] = useUrlFilter('end');
  const setFilters = useSetUrlFilters();
  const end = endParam ?? today();
  const start = startParam ?? daysBefore(end, 14);
  // Typed dates are applied together with the button, so a half-typed range is never sent.
  const [draft, setDraft] = useState({ start, end });
  const days = span(start, end);
  const rangeProblem =
    draft.end < draft.start
      ? 'The end date is before the start date.'
      : span(draft.start, draft.end) > MAX_DAYS
        ? `Pick at most ${MAX_DAYS} days at a time.`
        : null;

  const activity = useQuery({
    queryKey: ['admin', 'daily', start, end],
    queryFn: () => api<DailyActivity[]>('/admin/daily', { params: { start, end } }),
  });

  function choose(nextStart: string, nextEnd: string) {
    setDraft({ start: nextStart, end: nextEnd });
    // Both in one step: two separate changes would lose the first.
    setFilters({ start: nextStart, end: nextEnd });
  }

  const rows = activity.data ?? [];
  const totals = rows.reduce(
    (sum, day) => ({
      signups: sum.signups + day.signups,
      job_checks: sum.job_checks + day.job_checks,
      applications: sum.applications + day.applications,
    }),
    { signups: 0, job_checks: 0, applications: 0 },
  );

  return (
    <>
      <PageHeader
        title="Activity"
        subtitle="Sign-ups, job checks and applications per day, for any dates you pick. Days are in UTC."
      />

      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Quick ranges">
        {PRESETS.map((preset) => {
          const active = end === today() && days === preset;
          return (
            <button
              key={preset}
              onClick={() => choose(daysBefore(today(), preset), today())}
              aria-pressed={active}
              className={pill(active)}
            >
              Last {preset} days
            </button>
          );
        })}
      </div>

      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!rangeProblem) choose(draft.start, draft.end);
        }}
      >
        <label className="text-sm font-semibold text-zinc-700">
          From
          <input
            type="date"
            value={draft.start}
            max={today()}
            onChange={(event) => setDraft({ ...draft, start: event.target.value })}
            className="mt-1 block rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
            required
          />
        </label>
        <label className="text-sm font-semibold text-zinc-700">
          To
          <input
            type="date"
            value={draft.end}
            max={today()}
            onChange={(event) => setDraft({ ...draft, end: event.target.value })}
            className="mt-1 block rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
            required
          />
        </label>
        <button
          disabled={rangeProblem !== null}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
        >
          Show these dates
        </button>
        {rangeProblem && (
          <p role="alert" className="w-full text-sm font-medium text-red-700">
            {rangeProblem}
          </p>
        )}
      </form>

      {activity.isPending ? (
        <Card>
          <Loading rows={8} />
        </Card>
      ) : activity.isError ? (
        <Card>
          <ErrorNote message={errorMessage(activity.error)} onRetry={() => activity.refetch()} />
        </Card>
      ) : (
        <div className="space-y-6">
          <Card className="p-5">
            <h2 className="mb-1 font-bold">
              {formatDate(start)} to {formatDate(end)}{' '}
              <span className="font-normal text-zinc-500">
                ({days} {days === 1 ? 'day' : 'days'})
              </span>
            </h2>
            <p className="mb-4 text-sm text-zinc-500">
              {totals.signups} sign-ups · {totals.job_checks} job checks · {totals.applications}{' '}
              applications
            </p>
            <ActivityChart days={rows} />
          </Card>

          <Card>
            <h2 className="px-4 pt-4 pb-3 font-bold">Day by day</h2>
            {rows.length === 0 ? (
              <Empty>No days in this range.</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-y border-zinc-200">
                    <tr>
                      <th className={th}>Day</th>
                      <th className={th}>Sign-ups</th>
                      <th className={th}>Job checks</th>
                      <th className={th}>Applications</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {[...rows].reverse().map((day) => (
                      <tr key={day.day}>
                        <th scope="row" className={`${td} text-left font-semibold`}>
                          {formatDate(day.day)}
                        </th>
                        <Count value={day.signups} href={`/users?joined_on=${day.day}`} />
                        <Count value={day.job_checks} href={`/job-checks?day=${day.day}`} />
                        <Count value={day.applications} href={`/applications?day=${day.day}`} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}

/** A day's count; when there is anything to see, it opens that day's list. */
function Count({ value, href }: { value: number; href: string }) {
  return (
    <td className={`${td} tabular-nums`}>
      {value ? (
        <Link href={href} className="font-semibold text-blue-700 hover:underline">
          {value}
        </Link>
      ) : (
        <span className="text-zinc-400">0</span>
      )}
    </td>
  );
}

export default function ActivityPage() {
  return (
    <Suspense>
      <Activity />
    </Suspense>
  );
}
