'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

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
import { BulkEmail } from '@/components/BulkEmail';
import { api, errorMessage } from '@/lib/api';
import { formatDate, timeAgo } from '@/lib/format';
import type { UserPage } from '@/lib/types';

export default function UsersPage() {
  const [typed, setTyped] = useState('');
  const [search, setSearch] = useState('');
  const [withoutExtension, setWithoutExtension] = useState(false);
  const users = useInfiniteQuery({
    queryKey: ['admin', 'users', search, withoutExtension],
    queryFn: ({ pageParam }) =>
      api<UserPage>('/admin/users', {
        params: {
          q: search || undefined,
          extension: withoutExtension ? 'missing' : undefined,
          cursor: pageParam,
        },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const rows = users.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageHeader title="Users" subtitle="Search by email or name. Newest first.">
        <form
          role="search"
          className="flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(typed.trim());
          }}
        >
          <input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            aria-label="Search users"
            placeholder="Search users…"
            className="w-64 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-900"
          />
          <button className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-black">
            Search
          </button>
        </form>
      </PageHeader>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm font-semibold text-zinc-700">
          <input
            type="checkbox"
            checked={withoutExtension}
            onChange={(event) => setWithoutExtension(event.target.checked)}
            className="size-4 accent-zinc-900"
          />
          Only people without the extension
        </label>
        <BulkEmail />
      </div>
      <Card>
        {users.isPending ? (
          <Loading />
        ) : users.isError ? (
          <ErrorNote message={errorMessage(users.error)} onRetry={() => users.refetch()} />
        ) : rows.length === 0 ? (
          <Empty>{search ? 'No users match that search.' : 'Nobody has signed up yet.'}</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>User</th>
                  <th className={th}>Profile</th>
                  <th className={th}>Job checks</th>
                  <th className={th}>Applications</th>
                  <th className={th}>Gmail</th>
                  <th className={th}>Extension</th>
                  <th className={th}>Last check</th>
                  <th className={th}>Emailed</th>
                  <th className={th}>Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((user) => (
                  <tr key={user.id}>
                    <td className={td}>
                      <Link href={`/users/${user.id}`} className="block min-w-0">
                        <span className="block font-semibold hover:underline">
                          {user.name ?? user.email}
                        </span>
                        {user.name && (
                          <span className="block truncate text-xs text-zinc-500">{user.email}</span>
                        )}
                      </Link>
                    </td>
                    <td className={td}>
                      {user.has_profile ? (
                        <Badge tone="green">Yes</Badge>
                      ) : (
                        <Badge tone="amber">Not yet</Badge>
                      )}
                    </td>
                    <td className={td}>{user.job_checks}</td>
                    <td className={td}>{user.applications}</td>
                    <td className={td}>
                      {user.gmail_connected ? (
                        <Badge tone="blue">Connected</Badge>
                      ) : (
                        <span className="text-zinc-400">—</span>
                      )}
                    </td>
                    <td className={td}>
                      {user.extension_connected ? (
                        <Badge tone="blue">Connected</Badge>
                      ) : (
                        <span className="text-zinc-400">—</span>
                      )}
                    </td>
                    <td className={`${td} text-zinc-600`}>
                      {user.last_check_at ? timeAgo(user.last_check_at) : '—'}
                    </td>
                    <td className={`${td} text-zinc-600`}>
                      {user.last_emailed_at ? timeAgo(user.last_emailed_at) : '—'}
                    </td>
                    <td className={`${td} text-zinc-600`}>{formatDate(user.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <LoadMore
          show={users.hasNextPage}
          busy={users.isFetchingNextPage}
          onClick={() => users.fetchNextPage()}
        />
      </Card>
    </>
  );
}
