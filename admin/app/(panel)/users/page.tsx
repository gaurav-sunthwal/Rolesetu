'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Suspense, useState } from 'react';

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
import { BulkEmail } from '@/components/BulkEmail';
import { api, errorMessage } from '@/lib/api';
import { formatDate, timeAgo } from '@/lib/format';
import type { UserPage } from '@/lib/types';
import { useUrlFilter } from '@/lib/url-filter';

// The dashboard counts link here with one of these picked.
const FILTERS = [
  { value: null, label: 'Everyone' },
  { value: 'profile', label: 'With a profile' },
  { value: 'extension', label: 'Extension connected' },
  { value: 'extension_week', label: 'Used the extension in the last 7 days' },
  { value: 'no_extension', label: 'Without the extension' },
  { value: 'gmail', label: 'Gmail connected' },
] as const;

function Users() {
  const [typed, setTyped] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useUrlFilter('has');
  // Set by the Activity page, to list who signed up on one day.
  const [joinedOn, setJoinedOn] = useUrlFilter('joined_on');
  const withoutExtension = filter === 'no_extension';
  const users = useInfiniteQuery({
    queryKey: ['admin', 'users', search, filter, joinedOn],
    queryFn: ({ pageParam }) =>
      api<UserPage>('/admin/users', {
        params: {
          q: search || undefined,
          extension: withoutExtension ? 'missing' : undefined,
          has: filter && !withoutExtension ? filter : undefined,
          joined_on: joinedOn ?? undefined,
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
        <div className="flex flex-wrap gap-2" role="group" aria-label="Show">
          {FILTERS.map((option) => (
            <button
              key={option.label}
              onClick={() => setFilter(option.value)}
              aria-pressed={filter === option.value}
              className={pill(filter === option.value)}
            >
              {option.label}
            </button>
          ))}
          {joinedOn && (
            <button
              onClick={() => setJoinedOn(null)}
              className={pill(true)}
              title="Show people who joined on any day"
            >
              Joined {formatDate(joinedOn)} <span aria-hidden>×</span>
              <span className="sr-only">(remove)</span>
            </button>
          )}
        </div>
        <BulkEmail />
      </div>
      <Card>
        {users.isPending ? (
          <Loading />
        ) : users.isError ? (
          <ErrorNote message={errorMessage(users.error)} onRetry={() => users.refetch()} />
        ) : rows.length === 0 ? (
          <Empty>
            {search || filter || joinedOn ? 'No users match this.' : 'Nobody has signed up yet.'}
          </Empty>
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

export default function UsersPage() {
  return (
    <Suspense>
      <Users />
    </Suspense>
  );
}
