'use client';

import { useState } from 'react';

import type { EmailCompose } from '@/lib/types';

/**
 * Subject and message, prefilled with the suggested email. {first_name} is
 * replaced for each person. The "Add to Chrome" button, the link to connect
 * the extension and the footer are added by the server, not typed here.
 */
export function EmailComposer({
  initial,
  placeholder,
  sending,
  sendLabel,
  onSend,
}: {
  initial: EmailCompose;
  placeholder: string;
  sending: boolean;
  sendLabel: string;
  onSend: (email: EmailCompose) => void;
}) {
  const [subject, setSubject] = useState(initial.subject);
  const [message, setMessage] = useState(initial.message);
  const ready = subject.trim().length > 0 && message.trim().length > 0;
  const field =
    'w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-900';

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) onSend({ subject: subject.trim(), message: message.trim() });
      }}
    >
      <label className="block">
        <span className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">Subject</span>
        <input
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          maxLength={200}
          className={`${field} mt-1`}
        />
      </label>
      <label className="block">
        <span className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">Message</span>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          maxLength={5000}
          rows={9}
          className={`${field} mt-1 leading-relaxed`}
        />
      </label>
      <p className="text-xs text-zinc-500">
        <code className="rounded bg-zinc-100 px-1">{placeholder}</code> becomes each person&apos;s
        first name. An &ldquo;Add to Chrome&rdquo; button, a link to connect the extension and a
        note saying they can reply &ldquo;stop&rdquo; are added below your message.
      </p>
      <button
        disabled={!ready || sending}
        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
      >
        {sending ? 'Sending…' : sendLabel}
      </button>
    </form>
  );
}
