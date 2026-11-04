'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { ActivityChart } from '@/components/ActivityChart';
import { Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import type { AiCallSummary, Stats } from '@/lib/types';

type More = { href: string; label: string };

/** One count. The whole card opens the list behind it; `more` links open parts of it. */
function Stat({
  label,
  value,
  note,
  href,
  more = [],
}: {
  label: string;
  value: number;
  note?: string;
  href: string;
  more?: More[];
}) {
  return (
    <Card className="flex flex-col p-5 transition hover:ring-zinc-400">
      <Link href={href} className="group block rounded focus-visible:outline-2">
        <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</p>
        <p className="mt-2 text-3xl font-black tabular-nums">{value.toLocaleString('en-IN')}</p>
        {note && <p className="mt-1 text-xs text-zinc-500">{note}</p>}
        <p className="mt-2 text-xs font-semibold text-blue-700 group-hover:underline">
          See all <span aria-hidden>→</span>
        </p>
      </Link>
      {more.length > 0 && (
        <ul className="mt-2 space-y-0.5 border-t border-zinc-100 pt-2">
          {more.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="text-xs font-semibold text-zinc-600 hover:text-zinc-900 hover:underline"
              >
                {item.label} <span aria-hidden>→</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** The last two weeks; the Activity page shows any dates. */
function Daily({ days }: { days: Stats['daily'] }) {
  return (
    <Card className="p-5">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-bold">Last 14 days</h2>
        <Link
          href="/activity"
          className="text-sm font-semibold text-blue-700 hover:underline focus-visible:outline-2"
        >
          Pick dates and see each day <span aria-hidden>→</span>
        </Link>
      </div>
      <ActivityChart days={days} />
    </Card>
  );
}

export default function DashboardPage() {
  const stats = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => api<Stats>('/admin/stats'),
  });
  // Its own request, sent at the same time, so a problem with it only affects this card.
  const aiCalls = useQuery({
    queryKey: ['admin', 'ai-calls', 'summary', 24],
    queryFn: () => api<AiCallSummary>('/admin/ai-calls/summary', { params: { hours: '24' } }),
  });
  const aiBySource = aiCalls.data?.by_source ?? {};

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
              href="/users"
              more={[
                {
                  href: '/users?has=profile',
                  label: `${stats.data.users_with_profile} with a profile`,
                },
              ]}
            />
            <Stat label="Job checks" value={stats.data.job_checks} href="/job-checks" />
            <Stat
              label="Applications tracked"
              value={stats.data.applications}
              href="/applications"
            />
            <Stat
              label="Extension connected"
              value={stats.data.extension_connected}
              href="/users?has=extension"
              more={[
                {
                  href: '/users?has=extension_week',
                  label: `${stats.data.extension_active_week} used it in the last 7 days`,
                },
                { href: '/users?has=no_extension', label: 'People without it' },
              ]}
            />
            <Stat label="Extension waiting list" value={stats.data.waitlist} href="/waitlist" />
            <Stat
              label="Gmail connected"
              value={stats.data.gmail_connected}
              href="/users?has=gmail"
            />
            <Stat
              label="Landing previews"
              value={stats.data.previews_today}
              note="Job links read in the last 24 hours"
              href="/previews"
              more={[{ href: '/previews?show=failed', label: 'Ones that could not be read' }]}
            />
            <Stat
              label="Paid page reads"
              value={stats.data.paid_reads_today}
              note="Context.dev credits used in the last 24 hours"
              href="/paid-reads"
            />
            <Stat
              label="AI calls"
              value={aiCalls.data?.total ?? 0}
              note={
                aiCalls.isError
                  ? 'Could not load. Open to see why'
                  : aiCalls.data
                    ? `Last 24 hours: ${aiBySource.extension ?? 0} from the extension, ${aiBySource.resume ?? 0} from the resume editor`
                    : 'Loading…'
              }
              href="/ai-calls"
              more={[
                { href: '/ai-calls?source=extension', label: 'From the extension' },
                { href: '/ai-calls?source=resume', label: 'From the resume editor' },
              ]}
            />
            <Stat
              label="Errors"
              value={stats.data.errors_today}
              note={stats.data.errors_today ? 'In the last 24 hours' : 'None in the last 24 hours'}
              href="/errors"
            />
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
                        <td className={`${td} font-semibold`}>
                          <Link
                            href={`/previews?host=${encodeURIComponent(site.host)}`}
                            className="hover:underline"
                          >
                            {site.host}
                          </Link>
                        </td>
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
