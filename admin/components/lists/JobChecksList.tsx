'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { Badge, Card, Empty, ErrorNote, Loading, LoadMore, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { JobCheckPage } from '@/lib/types';

const STATUS = {
  completed: { label: 'Scored', tone: 'green' },
  pending: { label: 'Scoring', tone: 'amber' },
  failed: { label: 'Failed', tone: 'red' },
} as const;

/**
 * Everyone's job checks, newest first. `hours` limits the period, `day` (YYYY-MM-DD,
 * UTC) keeps one day's, and `paid` keeps paid reads.
 */
export function JobChecksList({
  hours,
  day = null,
  paid,
}: {
  hours: number | null;
  day?: string | null;
  paid: boolean;
}) {
  const checks = useInfiniteQuery({
    queryKey: ['admin', 'job-checks', hours, day, paid],
    queryFn: ({ pageParam }) =>
      api<JobCheckPage>('/admin/job-checks', {
        params: {
          hours: hours && !day ? String(hours) : undefined,
          day: day ?? undefined,
          paid: paid ? 'true' : undefined,
          cursor: pageParam,
        },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    staleTime: 0,
  });
  const rows = checks.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      {checks.isPending ? (
        <Loading />
      ) : checks.isError ? (
        <ErrorNote message={errorMessage(checks.error)} onRetry={() => checks.refetch()} />
      ) : rows.length === 0 ? (
        <Empty>No job checks in this period.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>When</th>
                <th className={th}>User</th>
                <th className={th}>Job</th>
                <th className={th}>Score</th>
                <th className={th}>Result</th>
                <th className={th}>Page read</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((check) => {
                const status = STATUS[check.status as keyof typeof STATUS] ?? {
                  label: check.status,
                  tone: 'zinc' as const,
                };
                const title = [check.role, check.company].filter(Boolean).join(' · ');
                return (
                  <tr key={check.id}>
                    <td className={`${td} whitespace-nowrap text-zinc-600`}>
                      {formatDateTime(check.created_at)}
                    </td>
                    <td className={td}>
                      <Link href={`/users/${check.user_id}`} className="hover:underline">
                        {check.user_email}
                      </Link>
                    </td>
                    <td className={`${td} max-w-sm`}>
                      {check.url ? (
                        <a
                          href={check.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="font-semibold hover:underline"
                        >
                          {title || check.url}
                        </a>
                      ) : (
                        <span className="font-semibold">{title || 'Pasted description'}</span>
                      )}
                    </td>
                    <td className={`${td} font-semibold tabular-nums`}>{check.score ?? '—'}</td>
                    <td className={td}>
                      <span title={check.error ?? undefined}>
                        <Badge tone={status.tone}>{status.label}</Badge>
                      </span>
                    </td>
                    <td className={td}>
                      {check.paid_read ? (
                        <Badge tone="amber">Paid reader</Badge>
                      ) : (
                        <span className="text-zinc-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore
        show={checks.hasNextPage}
        busy={checks.isFetchingNextPage}
        onClick={() => checks.fetchNextPage()}
      />
    </Card>
  );
}
