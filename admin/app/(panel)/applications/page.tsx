'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Suspense } from 'react';

import {
  Badge,
  Card,
  Empty,
  ErrorNote,
  Loading,
  LoadMore,
  PageHeader,
  pill,
  td,
  th,
} from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDate, formatDateTime } from '@/lib/format';
import type { ApplicationPage } from '@/lib/types';
import { useUrlFilter } from '@/lib/url-filter';

const TONES: Record<string, 'zinc' | 'green' | 'amber' | 'red' | 'blue'> = {
  saved: 'zinc',
  applied: 'blue',
  replied: 'blue',
  interview: 'amber',
  offer: 'green',
  rejected: 'red',
};

function Applications() {
  // Set by the Activity page, to list one day's applications.
  const [day, setDay] = useUrlFilter('day');
  const applications = useInfiniteQuery({
    queryKey: ['admin', 'applications', day],
    queryFn: ({ pageParam }) =>
      api<ApplicationPage>('/admin/applications', {
        params: { day: day ?? undefined, cursor: pageParam },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    staleTime: 0,
  });
  const rows = applications.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageHeader
        title="Applications tracked"
        subtitle="Every application any user is tracking, newest first."
      />
      {day && (
        <div className="mb-6">
          <button onClick={() => setDay(null)} className={pill(true)} title="Show every day">
            Added on {formatDate(day)} <span aria-hidden>×</span>
            <span className="sr-only">(remove)</span>
          </button>
        </div>
      )}
      <Card>
        {applications.isPending ? (
          <Loading />
        ) : applications.isError ? (
          <ErrorNote
            message={errorMessage(applications.error)}
            onRetry={() => applications.refetch()}
          />
        ) : rows.length === 0 ? (
          <Empty>
            {day
              ? 'No applications were added that day.'
              : 'Nobody is tracking an application yet.'}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>Added</th>
                  <th className={th}>User</th>
                  <th className={th}>Role</th>
                  <th className={th}>Company</th>
                  <th className={th}>Status</th>
                  <th className={th}>Score</th>
                  <th className={th}>Applied</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((item) => (
                  <tr key={item.id}>
                    <td className={`${td} whitespace-nowrap text-zinc-600`}>
                      {formatDateTime(item.created_at)}
                    </td>
                    <td className={td}>
                      <Link href={`/users/${item.user_id}`} className="hover:underline">
                        {item.user_email}
                      </Link>
                    </td>
                    <td className={`${td} font-semibold`}>{item.role}</td>
                    <td className={td}>{item.company}</td>
                    <td className={td}>
                      <Badge tone={TONES[item.status] ?? 'zinc'}>{item.status}</Badge>
                    </td>
                    <td className={`${td} tabular-nums`}>{item.match_score ?? '—'}</td>
                    <td className={`${td} whitespace-nowrap text-zinc-600`}>
                      {item.applied_at ? formatDate(item.applied_at) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <LoadMore
          show={applications.hasNextPage}
          busy={applications.isFetchingNextPage}
          onClick={() => applications.fetchNextPage()}
        />
      </Card>
    </>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense>
      <Applications />
    </Suspense>
  );
}
