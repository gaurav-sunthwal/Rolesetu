'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';

import { Badge, Card, ErrorNote, Loading, PageHeader, button } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { sourceLabel } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import type { ErrorEvent } from '@/lib/types';

export default function ErrorPage() {
  const { fingerprint } = useParams<{ fingerprint: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const events = useQuery({
    queryKey: ['admin', 'error', fingerprint],
    queryFn: () => api<ErrorEvent[]>(`/admin/errors/${fingerprint}`),
  });
  const clear = useMutation({
    mutationFn: () => api<void>(`/admin/errors/${fingerprint}`, { method: 'DELETE' }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      router.replace('/errors');
    },
  });

  const back = (
    <Link href="/errors" className="text-sm font-semibold text-zinc-500 hover:text-zinc-900">
      ← Errors
    </Link>
  );
  if (events.isPending) {
    return (
      <>
        {back}
        <Card className="mt-4">
          <Loading rows={8} />
        </Card>
      </>
    );
  }
  if (events.isError) {
    return (
      <>
        {back}
        <Card className="mt-4">
          <ErrorNote message={errorMessage(events.error)} onRetry={() => events.refetch()} />
        </Card>
      </>
    );
  }
  const latest = events.data[0];

  return (
    <div className="space-y-6">
      <div>
        {back}
        <PageHeader
          title={latest.code ?? 'Problem'}
          subtitle={`${sourceLabel(latest.source)}${latest.route ? ` · ${latest.method ? `${latest.method} ` : ''}${latest.route}` : ''}`}
        >
          <div className="text-right">
            <button onClick={() => clear.mutate()} disabled={clear.isPending} className={button}>
              {clear.isPending ? 'Clearing…' : 'Mark as dealt with'}
            </button>
            <p className="mt-1 text-xs text-zinc-500">
              Removes these events. Recorded in the audit log.
            </p>
          </div>
        </PageHeader>
        {clear.isError && (
          <p role="alert" className="text-sm font-medium text-red-700">
            {errorMessage(clear.error)}
          </p>
        )}
      </div>

      <Card className="p-4">
        <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">What it said</p>
        <p className="mt-1.5 font-semibold break-words">{latest.message}</p>
        {latest.stack ? (
          <>
            <p className="mt-5 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
              Where it broke (most recent)
            </p>
            <pre className="mt-1.5 max-h-96 overflow-auto rounded-lg bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-100">
              {latest.stack}
            </pre>
          </>
        ) : (
          <p className="mt-3 text-sm text-zinc-500">
            A failure we handled and told the person about, so there is no crash trace.
          </p>
        )}
      </Card>

      <Card>
        <h2 className="border-b border-zinc-200 px-4 py-3 font-bold">
          {events.data.length === 50
            ? 'Latest 50 times it happened'
            : `Each time it happened (${events.data.length})`}
        </h2>
        <ul className="divide-y divide-zinc-100 text-sm">
          {events.data.map((event) => (
            <li key={event.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
              <span className="whitespace-nowrap text-zinc-600">
                {formatDateTime(event.created_at)}
              </span>
              {event.status && (
                <Badge tone={event.status >= 500 ? 'red' : 'amber'}>{event.status}</Badge>
              )}
              <span className="min-w-0 flex-1 truncate">{event.message}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
