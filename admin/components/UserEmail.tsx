'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { EmailComposer } from '@/components/EmailComposer';
import { Badge, Card, Empty, ErrorNote, Loading } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { useEmailDefaults, useEmailTemplates } from '@/lib/outreach';
import type { EmailCompose, EmailTemplate, OutreachEmail } from '@/lib/types';

/**
 * Write to one person now, starting from a template filled in with what they
 * have done, and see what they were already sent from the panel.
 */
export function UserEmail({ userId, sent }: { userId: string; sent: OutreachEmail[] }) {
  const queryClient = useQueryClient();
  const defaults = useEmailDefaults();
  const templates = useEmailTemplates(userId);
  const [picked, setPicked] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: (email: EmailCompose) =>
      api<OutreachEmail>(`/admin/users/${userId}/email`, { method: 'POST', body: email }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'user', userId] }),
  });

  return (
    <Card>
      <h2 className="border-b border-zinc-200 px-4 py-3 font-bold">Email this person</h2>
      <div className="p-4">
        {defaults.isPending || templates.isPending ? (
          <Loading rows={4} />
        ) : defaults.isError ? (
          <ErrorNote message={errorMessage(defaults.error)} onRetry={() => defaults.refetch()} />
        ) : templates.isError ? (
          <ErrorNote message={errorMessage(templates.error)} onRetry={() => templates.refetch()} />
        ) : !defaults.data.configured ? (
          <p className="text-sm font-medium text-red-700">
            Email is not set up on the server. Add GMAIL_SENDER_REFRESH_TOKEN to the API to send
            from here.
          </p>
        ) : send.isSuccess && send.data.status === 'sent' ? (
          <p role="status" className="text-sm font-medium text-emerald-800">
            Sent. It is listed below.
          </p>
        ) : (
          <>
            <TemplatePicker
              templates={templates.data}
              picked={chosen(templates.data, picked)?.id ?? null}
              onPick={setPicked}
            />
            <EmailComposer
              // A new template starts the form again from its text.
              key={chosen(templates.data, picked)?.id ?? 'blank'}
              initial={chosen(templates.data, picked) ?? { subject: '', message: '' }}
              kind={chosen(templates.data, picked)?.kind ?? 'founder_note'}
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

/** The template picked, or the recommended one until the admin picks. */
function chosen(templates: EmailTemplate[], picked: string | null): EmailTemplate | undefined {
  return templates.find((t) => t.id === picked) ?? templates.find((t) => t.recommended);
}

function TemplatePicker({
  templates,
  picked,
  onPick,
}: {
  templates: EmailTemplate[];
  picked: string | null;
  onPick: (id: string) => void;
}) {
  return (
    <fieldset className="mb-4">
      <legend className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">
        Start from
      </legend>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {templates.map((template) => {
          const active = template.id === picked;
          return (
            <button
              key={template.id}
              type="button"
              onClick={() => onPick(template.id)}
              aria-pressed={active}
              className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                active ? 'border-zinc-900 bg-zinc-50' : 'border-zinc-200 hover:border-zinc-400'
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-semibold">
                {template.label}
                {template.recommended && <Badge tone="green">Best fit</Badge>}
              </span>
              <span className="mt-0.5 block text-xs text-zinc-500">{template.hint}</span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
