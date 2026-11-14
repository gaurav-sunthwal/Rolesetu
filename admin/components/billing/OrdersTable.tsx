'use client';

import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { ConfirmAction } from '@/components/billing/ConfirmAction';
import { Badge, Empty, td, th } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate, formatDateTime, formatMoney } from '@/lib/format';
import type { BillingOrder } from '@/lib/types';

type Tone = 'green' | 'amber' | 'red' | 'zinc';

/** Where a payment or given month stands, in words. */
export function stateOf(order: BillingOrder, now = Date.now()): { label: string; tone: Tone } {
  if (order.status === 'created') return { label: 'Not paid', tone: 'zinc' };
  if (order.status === 'refunded') return { label: 'Refunded', tone: 'red' };
  if (order.status === 'revoked') return { label: 'Removed', tone: 'red' };
  const starts = order.pro_starts_at ? Date.parse(order.pro_starts_at) : 0;
  const ends = order.pro_ends_at ? Date.parse(order.pro_ends_at) : 0;
  if (ends <= now) return { label: 'Ended', tone: 'zinc' };
  if (starts > now) return { label: 'Upcoming', tone: 'amber' };
  return { label: 'Pro now', tone: 'green' };
}

type Pending = { order: BillingOrder; kind: 'refund' | 'revoke' };

/**
 * Payments and given months, with what can be done to each: a paid payment can be
 * refunded (through Razorpay) or removed; a given month can be removed.
 */
export function OrdersTable({
  orders,
  showUser = true,
}: {
  orders: BillingOrder[];
  showUser?: boolean;
}) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<Pending | null>(null);

  if (orders.length === 0) return <Empty>No payments yet.</Empty>;

  async function act(order: BillingOrder, kind: Pending['kind'], note: string) {
    await api<BillingOrder>(`/admin/billing/orders/${order.id}/${kind}`, {
      method: 'POST',
      body: { note },
    });
    await queryClient.invalidateQueries({ queryKey: ['admin'] });
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-y border-zinc-200">
            <tr>
              <th className={th}>When</th>
              {showUser && <th className={th}>User</th>}
              <th className={th}>What</th>
              <th className={th}>Amount</th>
              <th className={th}>State</th>
              <th className={th}>Pro from – to</th>
              <th className={th}>Note</th>
              <th className={th}>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {orders.map((order) => {
              const state = stateOf(order);
              const live = order.status === 'paid' && state.label !== 'Ended';
              return (
                <tr key={order.id}>
                  <td className={`${td} whitespace-nowrap`}>
                    {formatDateTime(order.paid_at ?? order.created_at)}
                  </td>
                  {showUser && (
                    <td className={td}>
                      <Link
                        href={`/users/${order.user_id}`}
                        className="font-semibold hover:underline"
                      >
                        {order.user_email}
                      </Link>
                    </td>
                  )}
                  <td className={td}>
                    {order.kind === 'grant' ? 'Given by an admin' : 'Payment'}
                    {order.razorpay_url && (
                      <a
                        href={order.razorpay_url}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-2 text-xs text-blue-700 hover:underline"
                      >
                        Razorpay ↗
                      </a>
                    )}
                  </td>
                  <td className={`${td} tabular-nums`}>
                    {order.kind === 'grant' ? 'Free' : formatMoney(order.amount, order.currency)}
                  </td>
                  <td className={td}>
                    <Badge tone={state.tone}>{state.label}</Badge>
                  </td>
                  <td className={`${td} whitespace-nowrap text-zinc-600`}>
                    {order.pro_starts_at && order.pro_ends_at
                      ? `${formatDate(order.pro_starts_at)} – ${formatDate(order.pro_ends_at)}`
                      : '–'}
                  </td>
                  <td className={`${td} max-w-56 text-zinc-600`}>{order.note ?? '–'}</td>
                  <td className={`${td} text-right whitespace-nowrap`}>
                    {order.status === 'paid' && order.kind === 'payment' && (
                      <button
                        type="button"
                        onClick={() => setPending({ order, kind: 'refund' })}
                        className="rounded-lg px-2.5 py-1 text-xs font-semibold text-red-700 ring-1 ring-red-200 hover:bg-red-50"
                      >
                        Refund
                      </button>
                    )}
                    {live && (
                      <button
                        type="button"
                        onClick={() => setPending({ order, kind: 'revoke' })}
                        className="ml-2 rounded-lg px-2.5 py-1 text-xs font-semibold text-zinc-700 ring-1 ring-zinc-200 hover:bg-zinc-50"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pending?.kind === 'refund' && (
        <ConfirmAction
          title={`Refund ${formatMoney(pending.order.amount, pending.order.currency)}?`}
          confirmLabel="Refund through Razorpay"
          onConfirm={(note) => act(pending.order, 'refund', note)}
          onClose={() => setPending(null)}
        >
          <p>
            Razorpay sends the full amount back to {pending.order.user_email}. This cannot be
            undone.
          </p>
          <p>
            The Pro this payment bought ends now. Months bought after it move up, so they lose
            nothing else.
          </p>
        </ConfirmAction>
      )}
      {pending?.kind === 'revoke' && (
        <ConfirmAction
          title="Remove this month of Pro?"
          confirmLabel="Remove without refund"
          onConfirm={(note) => act(pending.order, 'revoke', note)}
          onClose={() => setPending(null)}
        >
          <p>
            {pending.order.user_email} loses the Pro this{' '}
            {pending.order.kind === 'grant' ? 'given month' : 'payment'} gave.
            {pending.order.kind === 'payment' && (
              <strong> No money is sent back: use Refund for that.</strong>
            )}
          </p>
        </ConfirmAction>
      )}
    </>
  );
}
