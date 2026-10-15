'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { EmailComposer } from '@/components/EmailComposer';
import { Card, ErrorNote, Loading, button } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { useEmailDefaults } from '@/lib/outreach';
import type { BulkQueued, EmailCompose } from '@/lib/types';

/** Writes to everyone who has not connected the extension and was not written to lately. */
export function BulkEmail() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const defaults = useEmailDefaults();
  const send = useMutation({
    mutationFn: (email: EmailCompose) =>
      api<BulkQueued>('/admin/emails/extension-nudge', { method: 'POST', body: email }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className={button}>
        Email everyone without the extension
      </button>
    );
  }

  return (
    <Card className="mb-6 w-full p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-bold">Email everyone without the extension</h2>
          {defaults.data && (
            <p className="mt-1 text-sm text-zinc-600">
              {defaults.data.recipients === 0
                ? 'Nobody to write to: everyone has the extension or was written to in the last 14 days.'
                : `${defaults.data.recipients} ${defaults.data.recipients === 1 ? 'person has' : 'people have'} not connected it and were not written to in the last 14 days.${defaults.data.recipients > defaults.data.max_per_send ? ` One send reaches the first ${defaults.data.max_per_send}; send again later for the rest.` : ''}`}
            </p>
          )}
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-sm font-semibold text-zinc-500 hover:text-zinc-900"
        >
          Close
        </button>
      </div>
      <div className="mt-4">
        {defaults.isPending ? (
          <Loading rows={4} />
        ) : defaults.isError ? (
          <ErrorNote message={errorMessage(defaults.error)} onRetry={() => defaults.refetch()} />
        ) : !defaults.data.configured ? (
          <p className="text-sm font-medium text-red-700">
            Email is not set up on the server. Add RESEND_API_KEY to the API to send from here.
          </p>
        ) : send.isSuccess ? (
          <p role="status" className="text-sm font-medium text-emerald-800">
            {send.data.queued === 0
              ? 'Nobody to write to right now.'
              : `Sending to ${send.data.queued} ${send.data.queued === 1 ? 'person' : 'people'}. It takes a minute; each person's page shows when theirs went out.`}
          </p>
        ) : (
          <>
            <EmailComposer
              initial={{ subject: defaults.data.subject, message: defaults.data.message }}
              placeholder={defaults.data.placeholder}
              sending={send.isPending}
              sendLabel={`Send to ${Math.min(defaults.data.recipients, defaults.data.max_per_send)} people`}
              onSend={(email) => send.mutate(email)}
            />
            {send.isError && (
              <p role="alert" className="mt-2 text-sm font-medium text-red-700">
                {errorMessage(send.error)}
              </p>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
