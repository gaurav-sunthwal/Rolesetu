'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import Link from 'next/link';

import {
  Badge,
  Card,
  Empty,
  ErrorNote,
  Loading,
  LoadMore,
  PageHeader,
  td,
  th,
} from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { AuditPage } from '@/lib/types';

const LABELS: Record<string, { label: string; tone: 'zinc' | 'red' | 'blue' }> = {
  'user.view': { label: 'Opened a user', tone: 'blue' },
  'user.delete': { label: 'Deleted an account', tone: 'red' },
  'waitlist.view': { label: 'Opened the waiting list', tone: 'zinc' },
};

export default function AuditLogPage() {
  const log = useInfiniteQuery({
    queryKey: ['admin', 'audit'],
    queryFn: ({ pageParam }) => api<AuditPage>('/admin/audit', { params: { cursor: pageParam } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    staleTime: 0,
  });
  const rows = log.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageHeader
        title="Audit log"
        subtitle="Every time an admin opened someone's data or deleted an account."
      />
      <Card>
        {log.isPending ? (
          <Loading />
        ) : log.isError ? (
          <ErrorNote message={errorMessage(log.error)} onRetry={() => log.refetch()} />
        ) : rows.length === 0 ? (
          <Empty>Nothing has been recorded yet.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>When</th>
                  <th className={th}>Admin</th>
                  <th className={th}>Action</th>
                  <th className={th}>Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((row) => {
                  const kind = LABELS[row.action] ?? { label: row.action, tone: 'zinc' as const };
                  return (
                    <tr key={row.id}>
                      <td className={`${td} whitespace-nowrap text-zinc-600`}>
                        {formatDateTime(row.created_at)}
                      </td>
                      <td className={td}>{row.admin_email}</td>
                      <td className={td}>
                        <Badge tone={kind.tone}>{kind.label}</Badge>
                      </td>
                      <td className={`${td} text-zinc-600`}>
                        {row.action === 'user.view' ? (
                          <Link href={`/users/${row.target_id}`} className="hover:underline">
                            {row.summary}
                          </Link>
                        ) : (
                          row.summary
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
          show={log.hasNextPage}
          busy={log.isFetchingNextPage}
          onClick={() => log.fetchNextPage()}
        />
      </Card>
    </>
  );
}
