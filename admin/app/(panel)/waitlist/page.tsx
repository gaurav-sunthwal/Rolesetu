'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { useState } from 'react';

import {
  Card,
  Empty,
  ErrorNote,
  Loading,
  LoadMore,
  PageHeader,
  button,
  td,
  th,
} from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { WaitlistPage } from '@/lib/types';

export default function WaitlistAdminPage() {
  const [copied, setCopied] = useState(false);
  const list = useInfiniteQuery({
    queryKey: ['admin', 'waitlist'],
    queryFn: ({ pageParam }) =>
      api<WaitlistPage>('/admin/waitlist', { params: { cursor: pageParam } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const rows = list.data?.pages.flatMap((page) => page.items) ?? [];

  async function copyAll() {
    await navigator.clipboard.writeText(rows.map((row) => row.email).join(', '));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <PageHeader
        title="Extension waiting list"
        subtitle="People who asked to be emailed when the extension is released."
      >
        {rows.length > 0 && (
          <button onClick={copyAll} className={button}>
            {copied
              ? 'Copied'
              : `Copy ${rows.length} ${rows.length === 1 ? 'address' : 'addresses'}${list.hasNextPage ? ' shown' : ''}`}
          </button>
        )}
      </PageHeader>
      <Card>
        {list.isPending ? (
          <Loading />
        ) : list.isError ? (
          <ErrorNote message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        ) : rows.length === 0 ? (
          <Empty>Nobody has joined the waiting list yet.</Empty>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>Email</th>
                <th className={th}>Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className={`${td} font-semibold`}>{row.email}</td>
                  <td className={`${td} text-zinc-600`}>{formatDateTime(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <LoadMore
          show={list.hasNextPage}
          busy={list.isFetchingNextPage}
          onClick={() => list.fetchNextPage()}
        />
      </Card>
    </>
  );
}
