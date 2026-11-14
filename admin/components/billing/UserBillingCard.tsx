'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ActionLog } from '@/components/billing/ActionLog';
import { ConfirmAction } from '@/components/billing/ConfirmAction';
import { OrdersTable } from '@/components/billing/OrdersTable';
import { Badge, button, Card, ErrorNote, Loading } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDate } from '@/lib/format';
import type { BillingOrder, UserBilling } from '@/lib/types';

const QUICK_DAYS = [7, 30, 90, 365];

function GiveForm({ userId, onDone }: { userId: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [days, setDays] = useState(30);
  const [note, setNote] = useState('');
  const give = useMutation({
    mutationFn: () =>
      api<BillingOrder>(`/admin/users/${userId}/billing/grant`, {
        method: 'POST',
        body: { days, note: note.trim() },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      onDone();
    },
  });

  return (
    <form
      className="space-y-3 border-t border-zinc-200 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        give.mutate();
      }}
    >
      <p className="text-sm font-semibold">Give Pro for free</p>
      <div className="flex flex-wrap items-end gap-2">
        {QUICK_DAYS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={days === preset}
            onClick={() => setDays(preset)}
            className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${
              days === preset ? 'bg-zinc-900 text-white' : 'ring-1 ring-zinc-200 hover:bg-zinc-50'
            }`}
          >
            {preset === 365 ? '1 year' : `${preset} days`}
          </button>
        ))}
        <label className="text-sm">
          <span className="sr-only">Days</span>
          <input
            type="number"
            min={1}
            max={366}
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            className="w-20 rounded-lg px-2 py-1.5 ring-1 ring-zinc-300"
          />{' '}
          days
        </label>
      </div>
      <label className="block text-sm">
        Reason (kept in the log)
        <input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={200}
          placeholder="e.g. Beta tester, made up for an outage"
          className="mt-1 block w-full max-w-lg rounded-lg px-3 py-2 ring-1 ring-zinc-300"
        />
      </label>
      {give.isError && (
        <p role="alert" className="text-sm text-red-700">
          {errorMessage(give.error)}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={give.isPending || note.trim().length < 3 || days < 1 || days > 366}
          className="rounded-lg bg-zinc-900 px-4 py-1.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
        >
          {give.isPending ? 'Giving…' : `Give ${days} days of Pro`}
        </button>
        <button type="button" onClick={onDone} className={button}>
          Cancel
        </button>
      </div>
      <p className="text-xs text-zinc-500">
        Starts when any paid time they have ends, so they never lose days they paid for.
      </p>
    </form>
  );
}

/** One user's plan, payments and given months, and what an admin can change. */
export function UserBillingCard({ userId, email }: { userId: string; email: string }) {
  const queryClient = useQueryClient();
  const [giving, setGiving] = useState(false);
  const [ending, setEnding] = useState(false);
  const billing = useQuery({
    queryKey: ['admin', 'user', userId, 'billing'],
    queryFn: () => api<UserBilling>(`/admin/users/${userId}/billing`),
  });

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200 px-4 py-3">
        <h2 className="font-bold">Plan and payments</h2>
        {billing.data && (
          <Badge tone={billing.data.plan === 'pro' ? 'green' : 'zinc'}>
            {billing.data.plan === 'pro'
              ? `Pro${billing.data.pro_until ? ` until ${formatDate(billing.data.pro_until)}` : ''}`
              : 'Free'}
          </Badge>
        )}
        <div className="ml-auto flex gap-2">
          {!giving && (
            <button type="button" onClick={() => setGiving(true)} className={button}>
              Give Pro
            </button>
          )}
          {billing.data?.pro_until && (
            <button
              type="button"
              onClick={() => setEnding(true)}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold text-red-700 ring-1 ring-red-200 hover:bg-red-50"
            >
              End Pro now
            </button>
          )}
        </div>
      </div>

      {giving && <GiveForm userId={userId} onDone={() => setGiving(false)} />}

      {billing.isPending ? (
        <Loading rows={3} />
      ) : billing.isError ? (
        <ErrorNote message={errorMessage(billing.error)} onRetry={() => void billing.refetch()} />
      ) : (
        <>
          <OrdersTable orders={billing.data.orders} showUser={false} />
          {billing.data.actions.length > 0 && (
            <div className="border-t border-zinc-200">
              <h3 className="px-4 pt-3 text-sm font-semibold">Changes by admins</h3>
              <ActionLog actions={billing.data.actions} showUser={false} />
            </div>
          )}
        </>
      )}

      {ending && (
        <ConfirmAction
          title={`End Pro for ${email} now?`}
          confirmLabel="End Pro without refund"
          onConfirm={async (note) => {
            await api(`/admin/users/${userId}/billing/end`, { method: 'POST', body: { note } });
            await queryClient.invalidateQueries({ queryKey: ['admin'] });
          }}
          onClose={() => setEnding(false)}
        >
          <p>Every running and upcoming month is removed, paid or given.</p>
          <p>
            <strong>No money is sent back.</strong> To refund a payment, use Refund on that payment
            instead.
          </p>
        </ConfirmAction>
      )}
    </Card>
  );
}
