'use client';

import { useInfiniteQuery } from '@tanstack/react-query';

import { Badge, Card, Empty, ErrorNote, Loading, LoadMore, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { PreviewPage } from '@/lib/types';

type Filters = { hours: number; host?: string | null; paid?: boolean; failed?: boolean };

/** Job links visitors pasted on the landing page, newest first. They belong to no user. */
export function PreviewsList({ hours, host = null, paid = false, failed = false }: Filters) {
  const previews = useInfiniteQuery({
    queryKey: ['admin', 'previews', hours, host, paid, failed],
    queryFn: ({ pageParam }) =>
      api<PreviewPage>('/admin/previews', {
        params: {
          hours: String(hours),
          host: host ?? undefined,
          paid: paid ? 'true' : undefined,
          failed: failed ? 'true' : undefined,
          cursor: pageParam,
        },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    staleTime: 0,
  });
  const rows = previews.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      {previews.isPending ? (
        <Loading />
      ) : previews.isError ? (
        <ErrorNote message={errorMessage(previews.error)} onRetry={() => previews.refetch()} />
      ) : rows.length === 0 ? (
        <Empty>No job links in this period.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>When</th>
                <th className={th}>Site</th>
                <th className={th}>Job</th>
                <th className={th}>Result</th>
                <th className={th}>Read by</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className={`${td} whitespace-nowrap text-zinc-600`}>
                    {formatDateTime(row.created_at)}
                  </td>
                  <td className={`${td} font-semibold`}>{row.host ?? '—'}</td>
                  <td className={`${td} max-w-sm`}>
                    {row.title || row.company ? (
                      [row.title, row.company].filter(Boolean).join(' · ')
                    ) : (
                      <span className="text-zinc-400">—</span>
                    )}
                  </td>
                  <td className={td}>
                    {row.read ? (
                      <Badge tone="green">Read</Badge>
                    ) : (
                      <Badge tone="red">Could not read</Badge>
                    )}
                  </td>
                  <td className={td}>
                    {row.reader === 'rendered' ? (
                      <Badge tone="amber">Paid reader</Badge>
                    ) : row.reader === 'direct' ? (
                      'Direct'
                    ) : (
                      <span className="text-zinc-400">Not fetched</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore
        show={previews.hasNextPage}
        busy={previews.isFetchingNextPage}
        onClick={() => previews.fetchNextPage()}
      />
    </Card>
  );
}
