'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { Badge, Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { PERIODS, SOURCES, sourceLabel } from '@/lib/errors';
import { timeAgo } from '@/lib/format';
import type { ErrorSummary } from '@/lib/types';

const pill = (active: boolean) =>
  `rounded-lg px-3 py-1.5 text-sm font-semibold ${active ? 'bg-zinc-900 text-white' : 'bg-white text-zinc-600 ring-1 ring-zinc-200 hover:text-black'}`;

export default function ErrorsPage() {
  const [hours, setHours] = useState<number>(24);
  const [source, setSource] = useState<string | null>(null);
  const errors = useQuery({
    queryKey: ['admin', 'errors', hours, source],
    queryFn: () =>
      api<ErrorSummary>('/admin/errors', {
        params: { hours: String(hours), source: source ?? undefined },
      }),
    // Kept fresh while the page is open, so a new problem shows up on its own.
    refetchInterval: 30_000,
    staleTime: 0,
  });
  const bySource = errors.data?.by_source ?? {};
  const total = Object.values(bySource).reduce((sum, count) => sum + count, 0);
  const sources = [...new Set([...Object.keys(SOURCES), ...Object.keys(bySource)])];

  return (
    <>
      <PageHeader
        title="Errors"
        subtitle="Everything that went wrong, grouped by problem. Most frequent first."
      >
        <p className="text-xs text-zinc-500">Refreshes every 30 seconds</p>
      </PageHeader>

      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Period">
        {PERIODS.map((period) => (
          <button
            key={period.hours}
            onClick={() => setHours(period.hours)}
            aria-pressed={hours === period.hours}
            className={pill(hours === period.hours)}
          >
            {period.label}
          </button>
        ))}
      </div>
      <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Where it happened">
        <button
          onClick={() => setSource(null)}
          aria-pressed={source === null}
          className={pill(source === null)}
        >
          Everything <span className={total ? 'text-red-500' : 'opacity-50'}>{total}</span>
        </button>
        {sources.map((name) => {
          const count = bySource[name] ?? 0;
          return (
            <button
              key={name}
              onClick={() => setSource(name)}
              aria-pressed={source === name}
              title={SOURCES[name]?.help}
              className={pill(source === name)}
            >
              {sourceLabel(name)}{' '}
              <span className={count ? 'text-red-500' : 'opacity-50'}>{count}</span>
            </button>
          );
        })}
      </div>

      <Card>
        {errors.isPending ? (
          <Loading />
        ) : errors.isError ? (
          <ErrorNote message={errorMessage(errors.error)} onRetry={() => errors.refetch()} />
        ) : errors.data.groups.length === 0 ? (
          <Empty>Nothing went wrong in this period.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>Problem</th>
                  <th className={th}>Where</th>
                  <th className={th}>Times</th>
                  <th className={th}>Last seen</th>
                  <th className={th}>First seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {errors.data.groups.map((group) => (
                  <tr key={group.fingerprint}>
                    <td className={`${td} max-w-xl`}>
                      <Link href={`/errors/${group.fingerprint}`} className="block">
                        <span className="flex flex-wrap items-center gap-2">
                          <Badge tone={group.level === 'error' ? 'red' : 'amber'}>
                            {group.level === 'error' ? 'Crash' : 'Failure'}
                          </Badge>
                          {group.code && <span className="font-mono text-xs">{group.code}</span>}
                          {group.status && (
                            <span className="text-xs text-zinc-500">{group.status}</span>
                          )}
                        </span>
                        <span className="mt-1 line-clamp-2 block font-semibold hover:underline">
                          {group.message}
                        </span>
                      </Link>
                    </td>
                    <td className={td}>
                      <span className="block font-semibold">{sourceLabel(group.source)}</span>
                      {group.route && (
                        <span className="block font-mono text-xs break-all text-zinc-500">
                          {group.method ? `${group.method} ` : ''}
                          {group.route}
                        </span>
                      )}
                    </td>
                    <td className={`${td} font-semibold tabular-nums`}>{group.events}</td>
                    <td className={`${td} whitespace-nowrap text-zinc-600`}>
                      {timeAgo(group.last_at)}
                    </td>
                    <td className={`${td} whitespace-nowrap text-zinc-600`}>
                      {timeAgo(group.first_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
