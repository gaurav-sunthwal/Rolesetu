'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { EmailComposer } from '@/components/EmailComposer';
import { Badge, Card, Empty, ErrorNote, Loading } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { useEmailDefaults } from '@/lib/outreach';
import type { EmailCompose, OutreachEmail } from '@/lib/types';

/** Write to one person now, and see what they were already sent from the panel. */
export function UserEmail({
  userId,
  extensionConnected,
  sent,
}: {
  userId: string;
  extensionConnected: boolean;
  sent: OutreachEmail[];
}) {
  const queryClient = useQueryClient();
  const defaults = useEmailDefaults();
  const send = useMutation({
    mutationFn: (email: EmailCompose) =>
      api<OutreachEmail>(`/admin/users/${userId}/email`, { method: 'POST', body: email }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'user', userId] }),
  });

  return (
    <Card>
      <h2 className="border-b border-zinc-200 px-4 py-3 font-bold">Email this person</h2>
      <div className="p-4">
        {extensionConnected && (
          <p className="mb-3 text-sm text-zinc-600">
            They have already connected the extension, so the suggested email may not fit. Edit it
            first.
          </p>
        )}
        {defaults.isPending ? (
          <Loading rows={4} />
        ) : defaults.isError ? (
          <ErrorNote message={errorMessage(defaults.error)} onRetry={() => defaults.refetch()} />
        ) : !defaults.data.configured ? (
          <p className="text-sm font-medium text-red-700">
            Email is not set up on the server. Add RESEND_API_KEY to the API to send from here.
          </p>
        ) : send.isSuccess && send.data.status === 'sent' ? (
          <p role="status" className="text-sm font-medium text-emerald-800">
            Sent. It is listed below.
          </p>
        ) : (
          <>
            <EmailComposer
              initial={{ subject: defaults.data.subject, message: defaults.data.message }}
              placeholder={defaults.data.placeholder}
              sending={send.isPending}
              sendLabel="Send email"
              onSend={(email) => send.mutate(email)}
            />
            {send.isError && (
              <p role="alert" className="mt-2 text-sm font-medium text-red-700">
                {errorMessage(send.error)}
              </p>
            )}
            {send.isSuccess && send.data.status === 'failed' && (
              <p role="alert" className="mt-2 text-sm font-medium text-red-700">
                {send.data.error ?? 'It did not send. Try again later.'}
              </p>
            )}
          </>
        )}
      </div>
      <div className="border-t border-zinc-200">
        <p className="px-4 pt-3 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
          Sent from the panel
        </p>
        {sent.length === 0 ? (
          <Empty>Nothing sent yet.</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100 text-sm">
            {sent.map((email) => (
              <li key={email.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                <span className="whitespace-nowrap text-zinc-600">
                  {formatDateTime(email.created_at)}
                </span>
                <Badge tone={email.status === 'sent' ? 'green' : 'red'}>{email.status}</Badge>
                <span className="min-w-0 flex-1 truncate font-semibold">{email.subject}</span>
                <span className="text-xs text-zinc-500">by {email.admin_email}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
