'use client';

import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
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
  td,
  th,
} from '@/components/ui';
import { api, ApiError, errorMessage } from '@/lib/api';
import { PERIODS } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import type { AiCallPage, AiCallSummary } from '@/lib/types';
import { useUrlFilter } from '@/lib/url-filter';

const SOURCES: Record<string, { label: string; help: string }> = {
  extension: { label: 'Extension', help: 'Job checks from the browser extension' },
  resume: { label: 'Resume editor', help: "The resume editor's assistant" },
  dashboard: { label: 'Dashboard job checks', help: 'Job checks from the website' },
  other: { label: 'Other', help: 'Scripts and evals' },
};

const PURPOSES: Record<string, string> = {
  'job-read': 'Read the job',
  'skill-judge': 'Judge skills',
  'resume-assistant': 'Resume assistant',
};

/**
 * Counting AI calls is newer than the rest of the panel, so an API that has not
 * been updated yet answers 404 (no such page) or 500 (no table yet). Say which
 * step is missing instead of showing "Not Found".
 */
function callsError(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return 'This API does not count AI calls yet. Deploy the latest backend, run the database migration (uv run alembic upgrade head), then reload this page.';
  }
  if (error instanceof ApiError && error.status === 500) {
    return 'The API could not read the AI calls. If the backend was just deployed, run the database migration (uv run alembic upgrade head), then reload this page.';
  }
  return errorMessage(error);
}

const sourceLabel = (name: string) => SOURCES[name]?.label ?? name;
const count = (value: number) => value.toLocaleString('en-IN');

const pill = (active: boolean) =>
  `rounded-lg px-3 py-1.5 text-sm font-semibold ${active ? 'bg-zinc-900 text-white' : 'bg-white text-zinc-600 ring-1 ring-zinc-200 hover:text-black'}`;

function Totals({ summary }: { summary: AiCallSummary }) {
  const items = [
    { label: 'Calls', value: count(summary.total) },
    { label: 'Failed', value: count(summary.failed) },
    { label: "On the user's own key", value: count(summary.own_key) },
    {
      label: 'Tokens in / out',
      value: `${count(summary.input_tokens)} / ${count(summary.output_tokens)}`,
    },
  ];
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label} className="p-4">
          <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">
            {item.label}
          </p>
          <p className="mt-1 text-2xl font-black tabular-nums">{item.value}</p>
        </Card>
      ))}
    </div>
  );
}

function AiCalls() {
  const [hours, setHours] = useState<number>(24);
  // In the address, so the dashboard can link straight to one source.
  const [source, setSource] = useUrlFilter('source');

  const summary = useQuery({
    queryKey: ['admin', 'ai-calls', 'summary', hours],
    queryFn: () =>
      api<AiCallSummary>('/admin/ai-calls/summary', { params: { hours: String(hours) } }),
    staleTime: 0,
  });
  const calls = useInfiniteQuery({
    queryKey: ['admin', 'ai-calls', hours, source],
    queryFn: ({ pageParam }) =>
      api<AiCallPage>('/admin/ai-calls', {
        params: { hours: String(hours), source: source ?? undefined, cursor: pageParam },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    staleTime: 0,
  });
  const rows = calls.data?.pages.flatMap((page) => page.items) ?? [];
  const bySource = summary.data?.by_source ?? {};
  const sources = [...new Set([...Object.keys(SOURCES), ...Object.keys(bySource)])];

  return (
    <>
      <PageHeader
        title="AI calls"
        subtitle="Every request to the model, newest first: where it came from, who it was for and what it cost."
      />

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
      <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Where it came from">
        <button
          onClick={() => setSource(null)}
          aria-pressed={source === null}
          className={pill(source === null)}
        >
          Everything <span className="opacity-60">{summary.data?.total ?? '…'}</span>
        </button>
        {sources.map((name) => (
          <button
            key={name}
            onClick={() => setSource(name)}
            aria-pressed={source === name}
            title={SOURCES[name]?.help}
            className={pill(source === name)}
          >
            {sourceLabel(name)}{' '}
            <span className="opacity-60">{summary.data ? (bySource[name] ?? 0) : '…'}</span>
          </button>
        ))}
      </div>

      {summary.isError ? (
        <Card className="mb-6">
          <ErrorNote message={callsError(summary.error)} onRetry={() => summary.refetch()} />
        </Card>
      ) : summary.data ? (
        <Totals summary={summary.data} />
      ) : null}

      <Card>
        {calls.isPending ? (
          <Loading />
        ) : calls.isError ? (
          <ErrorNote message={callsError(calls.error)} onRetry={() => calls.refetch()} />
        ) : rows.length === 0 ? (
          <Empty>No AI calls in this period.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200">
                <tr>
                  <th className={th}>When</th>
                  <th className={th}>Where</th>
                  <th className={th}>For</th>
                  <th className={th}>User</th>
                  <th className={th}>Model</th>
                  <th className={th}>Tokens in / out</th>
                  <th className={th}>Took</th>
                  <th className={th}>Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((call) => (
                  <tr key={call.id}>
                    <td className={`${td} whitespace-nowrap text-zinc-600`}>
                      {formatDateTime(call.created_at)}
                    </td>
                    <td className={`${td} font-semibold whitespace-nowrap`}>
                      {sourceLabel(call.source)}
                    </td>
                    <td className={`${td} whitespace-nowrap`}>
                      {PURPOSES[call.purpose] ?? call.purpose}
                    </td>
                    <td className={td}>
                      {call.user_id ? (
                        <Link href={`/users/${call.user_id}`} className="hover:underline">
                          {call.user_email ?? 'Unknown user'}
                        </Link>
                      ) : (
                        <span className="text-zinc-500">No user</span>
                      )}
                    </td>
                    <td className={td}>
                      <span className="block font-mono text-xs">{call.model ?? '—'}</span>
                      {call.own_key && <span className="text-xs text-zinc-500">Own key</span>}
                    </td>
                    <td className={`${td} whitespace-nowrap tabular-nums`}>
                      {call.input_tokens ?? '—'} / {call.output_tokens ?? '—'}
                    </td>
                    <td className={`${td} whitespace-nowrap tabular-nums`}>
                      {(call.duration_ms / 1000).toFixed(1)}s
                    </td>
                    <td className={td}>
                      {call.ok ? (
                        <Badge tone="green">Answered</Badge>
                      ) : (
                        <span title={call.error ?? undefined}>
                          <Badge tone="red">Failed</Badge>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <LoadMore
          show={calls.hasNextPage}
          busy={calls.isFetchingNextPage}
          onClick={() => calls.fetchNextPage()}
        />
      </Card>
    </>
  );
}

export default function AiCallsPage() {
  return (
    <Suspense>
      <AiCalls />
    </Suspense>
  );
}
