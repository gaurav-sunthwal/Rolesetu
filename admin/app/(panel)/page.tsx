'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDay } from '@/lib/format';
import type { Stats } from '@/lib/types';

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</p>
      <p className="mt-2 text-3xl font-black tabular-nums">{value.toLocaleString('en-IN')}</p>
      {note && <p className="mt-1 text-xs text-zinc-500">{note}</p>}
    </Card>
  );
}

/** Two bars per day: sign-ups and job checks. Read out as a table for screen readers. */
function Daily({ days }: { days: Stats['daily'] }) {
  const top = Math.max(1, ...days.map((day) => Math.max(day.signups, day.job_checks)));
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-bold">Last 14 days</h2>
        <p className="flex gap-4 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-zinc-900" /> Sign-ups
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-blue-500" /> Job checks
          </span>
        </p>
      </div>
      <div className="mt-5 flex h-40 items-end gap-1.5" aria-hidden>
        {days.map((day) => (
          <div key={day.day} className="flex h-full flex-1 flex-col justify-end gap-1">
            <div className="flex flex-1 items-end gap-0.5">
              <div
                className="flex-1 rounded-t bg-zinc-900"
                style={{ height: `${(day.signups / top) * 100}%` }}
                title={`${day.signups} sign-ups`}
              />
              <div
                className="flex-1 rounded-t bg-blue-500"
                style={{ height: `${(day.job_checks / top) * 100}%` }}
                title={`${day.job_checks} job checks`}
              />
            </div>
            <p className="truncate text-center text-[10px] text-zinc-500">{formatDay(day.day)}</p>
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>Sign-ups and job checks per day</caption>
        <tbody>
          {days.map((day) => (
            <tr key={day.day}>
              <th scope="row">{formatDay(day.day)}</th>
              <td>{day.signups} sign-ups</td>
              <td>{day.job_checks} job checks</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export default function DashboardPage() {
  const stats = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => api<Stats>('/admin/stats'),
  });

  return (
    <>
      <PageHeader title="Dashboard" subtitle="How Rolesetu is being used." />
      {stats.isPending ? (
        <Card>
          <Loading rows={8} />
        </Card>
      ) : stats.isError ? (
        <Card>
          <ErrorNote message={errorMessage(stats.error)} onRetry={() => stats.refetch()} />
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Users"
              value={stats.data.users}
              note={`${stats.data.users_with_profile} with a profile`}
            />
            <Stat label="Job checks" value={stats.data.job_checks} />
            <Stat label="Applications tracked" value={stats.data.applications} />
            <Stat
              label="Extension connected"
              value={stats.data.extension_connected}
              note={`${stats.data.extension_active_week} used it in the last 7 days`}
            />
            <Stat label="Extension waiting list" value={stats.data.waitlist} />
            <Stat label="Gmail connected" value={stats.data.gmail_connected} />
            <Stat
              label="Landing previews"
              value={stats.data.previews_today}
              note="Job links read in the last 24 hours"
            />
            <Stat
              label="Paid page reads"
              value={stats.data.paid_reads_today}
              note="Context.dev credits used in the last 24 hours"
            />
            <Link href="/errors" className="block rounded-xl focus-visible:outline-2">
              <Stat
                label="Errors"
                value={stats.data.errors_today}
                note={
                  stats.data.errors_today
                    ? 'In the last 24 hours. Open to see them'
                    : 'None in the last 24 hours'
                }
              />
            </Link>
          </div>
          <Daily days={stats.data.daily} />
          <Card>
            <h2 className="px-4 pt-4 font-bold">Job links pasted on the landing page</h2>
            <p className="px-4 pb-3 text-sm text-zinc-500">
              Last 24 hours, by site. A high failed count means that site needs work.
            </p>
            {stats.data.sites.length === 0 ? (
              <Empty>No job links in the last 24 hours.</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-y border-zinc-200">
                    <tr>
                      <th className={th}>Site</th>
                      <th className={th}>Read</th>
                      <th className={th}>Failed</th>
                      <th className={th}>Paid reads</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {stats.data.sites.map((site) => (
                      <tr key={site.host}>
                        <td className={`${td} font-semibold`}>{site.host}</td>
                        <td className={td}>{site.read}</td>
                        <td className={`${td} ${site.failed ? 'font-semibold text-red-700' : ''}`}>
                          {site.failed}
                        </td>
                        <td className={td}>{site.paid}</td>
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
