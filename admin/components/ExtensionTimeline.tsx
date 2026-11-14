'use client';

import { useQuery } from '@tanstack/react-query';

import { Card, Empty, ErrorNote, Loading, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { ExtEventRead } from '@/lib/types';

/** Labels, as an admin reads them: "source: pitch · mode: write". */
function describe(props: ExtEventRead['props']): string {
  if (!props) return '';
  return Object.entries(props)
    .map(([key, value]) => `${key.replace('_', ' ')}: ${String(value)}`)
    .join(' · ');
}

type Source = { userId: string; installId?: never } | { installId: string; userId?: never };

/**
 * Latest extension events, newest first: one user's ("autofill did nothing on that
 * site"), or one install's from the moment it was installed, signed in or not.
 * Counts and labels only, never what anyone typed.
 */
export function ExtensionTimeline({
  userId,
  installId,
  title = 'Extension activity',
}: Source & { title?: string }) {
  const events = useQuery({
    queryKey: installId
      ? ['admin', 'install', installId, 'events']
      : ['admin', 'user', userId, 'ext-events'],
    queryFn: () =>
      installId
        ? api<ExtEventRead[]>(`/admin/ext-installs/${installId}/events`)
        : api<ExtEventRead[]>(`/admin/users/${userId}/ext-events`, { params: { limit: '100' } }),
  });

  return (
    <Card>
      <h2 className="border-b border-zinc-200 px-4 py-3 font-bold">{title}</h2>
      {events.isPending ? (
        <Loading rows={4} />
      ) : events.isError ? (
        <ErrorNote message={errorMessage(events.error)} onRetry={() => void events.refetch()} />
      ) : events.data.length === 0 ? (
        <Empty>No extension activity in the last 90 days.</Empty>
      ) : (
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 border-b border-zinc-200 bg-white">
              <tr>
                <th className={th}>When</th>
                <th className={th}>What</th>
                <th className={th}>Site</th>
                <th className={th}>Details</th>
                <th className={th}>Version</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {events.data.map((event, index) => (
                <tr key={`${event.at}-${index}`}>
                  <td className={`${td} whitespace-nowrap`}>{formatDateTime(event.at)}</td>
                  <td className={`${td} font-medium`}>{event.name.replaceAll('_', ' ')}</td>
                  <td className={td}>{event.host ?? '–'}</td>
                  <td className={`${td} text-zinc-600`}>
                    {[event.count !== null ? `count: ${event.count}` : '', describe(event.props)]
                      .filter(Boolean)
                      .join(' · ') || '–'}
                  </td>
                  <td className={`${td} font-mono`}>{event.version ?? '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
