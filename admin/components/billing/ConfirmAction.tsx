'use client';

import { useEffect, useRef, useState } from 'react';

import { button } from '@/components/ui';
import { errorMessage } from '@/lib/api';

/**
 * Asks before a change to someone's money or Pro, with the reason it is logged
 * under. Built on the browser's <dialog>: focus stays inside, Escape cancels.
 */
export function ConfirmAction({
  title,
  children,
  confirmLabel,
  danger = true,
  onConfirm,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: (note: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const ready = note.trim().length >= 3 && !busy;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm(note.trim());
      onClose();
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={() => {
        if (!busy) onClose();
      }}
      onCancel={(event) => {
        if (busy) event.preventDefault();
      }}
      aria-labelledby="confirm-title"
      className="m-auto w-[min(480px,calc(100vw-2rem))] rounded-xl bg-white p-0 shadow-2xl backdrop:bg-zinc-950/60"
    >
      <form
        method="dialog"
        className="space-y-4 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) void confirm();
        }}
      >
        <h2 id="confirm-title" className="text-lg font-bold">
          {title}
        </h2>
        <div className="space-y-2 text-sm text-zinc-700">{children}</div>
        <label className="block text-sm font-semibold">
          Reason (kept in the log)
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={200}
            autoFocus
            placeholder="e.g. Support request, charged twice"
            className="mt-1 block w-full rounded-lg px-3 py-2 font-normal ring-1 ring-zinc-300 focus:ring-2 focus:ring-zinc-900 focus:outline-none"
          />
        </label>
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className={button}>
            Cancel
          </button>
          <button
            type="submit"
            disabled={!ready}
            className={`rounded-lg px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50 ${
              danger ? 'bg-red-600 hover:bg-red-700' : 'bg-zinc-900 hover:bg-black'
            }`}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </form>
    </dialog>
  );
}
