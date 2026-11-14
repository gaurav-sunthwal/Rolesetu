'use client';

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ActionLog } from '@/components/billing/ActionLog';
import { OrdersTable } from '@/components/billing/OrdersTable';
import {
  Badge,
  button,
  Card,
  Empty,
  ErrorNote,
  Loading,
  LoadMore,
  PageHeader,
  pill,
} from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime, formatMoney } from '@/lib/format';
import type { BillingOrderPage, BillingOverview, BillingPlan } from '@/lib/types';

const FILTERS = [
  { label: 'All', status: undefined, kind: undefined },
  { label: 'Paid', status: 'paid', kind: 'payment' },
  { label: 'Given free', status: undefined, kind: 'grant' },
  { label: 'Refunded', status: 'refunded', kind: undefined },
  { label: 'Removed', status: 'revoked', kind: undefined },
  { label: 'Not paid', status: 'created', kind: undefined },
] as const;

function Metric({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</p>
      <p className="mt-1 text-3xl font-bold tabular-nums">{value}</p>
      {note && <p className="mt-1 text-xs text-zinc-500">{note}</p>}
    </Card>
  );
}

/** Changes a plan's price, length and whether it can be bought. */
function PlanEditor({ plan }: { plan: BillingPlan }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [rupees, setRupees] = useState(String(plan.amount / 100));
  const [days, setDays] = useState(plan.days);
  const [description, setDescription] = useState(plan.description);
  const [active, setActive] = useState(plan.active);
  const [note, setNote] = useState('');
  const amount = Math.round(Number(rupees) * 100);
  const valid =
    Number.isFinite(amount) &&
    amount >= 100 &&
    days >= 1 &&
    days <= 366 &&
    description.trim().length >= 3;

  const save = useMutation({
    mutationFn: () =>
      api<BillingPlan>(`/admin/billing/plans/${plan.plan}`, {
        method: 'PUT',
        body: { amount, days, description: description.trim(), active, note: note.trim() || null },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'billing'] });
      setEditing(false);
      setNote('');
    },
  });

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-3 p-4">
        <div className="min-w-0 flex-1">
          <p className="font-semibold">
            {plan.description}{' '}
            <Badge tone={plan.active ? 'green' : 'red'}>
              {plan.active ? 'On sale' : 'Not on sale'}
            </Badge>
          </p>
          <p className="text-sm text-zinc-600">
            {formatMoney(plan.amount, plan.currency)} for {plan.days} days
            {plan.updated_by && plan.updated_at
              ? ` · changed by ${plan.updated_by}, ${formatDateTime(plan.updated_at)}`
              : ' · the starting price'}
          </p>
        </div>
        <button type="button" onClick={() => setEditing(true)} className={button}>
          Change price
        </button>
      </div>
    );
  }

  return (
    <form
      className="space-y-3 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <div className="flex flex-wrap gap-4">
        <label className="text-sm font-semibold">
          Price (₹)
          <input
            type="number"
            min={1}
            step="0.01"
            value={rupees}
            onChange={(event) => setRupees(event.target.value)}
            className="mt-1 block w-28 rounded-lg px-3 py-2 font-normal ring-1 ring-zinc-300"
          />
        </label>
        <label className="text-sm font-semibold">
          Days of Pro
          <input
            type="number"
            min={1}
            max={366}
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            className="mt-1 block w-24 rounded-lg px-3 py-2 font-normal ring-1 ring-zinc-300"
          />
        </label>
        <label className="min-w-64 flex-1 text-sm font-semibold">
          Name on the receipt
          <input
            value={description}
            maxLength={120}
            onChange={(event) => setDescription(event.target.value)}
            className="mt-1 block w-full rounded-lg px-3 py-2 font-normal ring-1 ring-zinc-300"
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={active}
          onChange={(event) => setActive(event.target.checked)}
        />
        On sale (off: nobody can buy it; people who have Pro keep it)
      </label>
      <label className="block text-sm font-semibold">
        Why (optional, kept in the log)
        <input
          value={note}
          maxLength={200}
          onChange={(event) => setNote(event.target.value)}
          className="mt-1 block w-full max-w-lg rounded-lg px-3 py-2 font-normal ring-1 ring-zinc-300"
        />
      </label>
      <p className="text-sm text-amber-800">
        Applies to the next payment at once. People who already paid keep what they paid for.
      </p>
      {save.isError && (
        <p role="alert" className="text-sm text-red-700">
          {errorMessage(save.error)}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!valid || save.isPending}
          className="rounded-lg bg-zinc-900 px-4 py-1.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
        >
          {save.isPending ? 'Saving…' : 'Save price'}
        </button>
        <button type="button" onClick={() => setEditing(false)} className={button}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Orders() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>(FILTERS[0]);
  const list = useInfiniteQuery({
    queryKey: ['admin', 'billing', 'orders', filter.label],
    queryFn: ({ pageParam }) =>
      api<BillingOrderPage>('/admin/billing/orders', {
        params: { cursor: pageParam, status: filter.status, kind: filter.kind },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const rows = list.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 px-4 py-3">
        <h2 className="mr-auto font-bold">Payments and given months</h2>
        {FILTERS.map((option) => (
          <button
            key={option.label}
            type="button"
            aria-pressed={filter.label === option.label}
            onClick={() => setFilter(option)}
            className={pill(filter.label === option.label)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {list.isPending ? (
        <Loading rows={5} />
      ) : list.isError ? (
        <ErrorNote message={errorMessage(list.error)} onRetry={() => void list.refetch()} />
      ) : (
        <OrdersTable orders={rows} />
      )}
      <LoadMore
        show={list.hasNextPage}
        busy={list.isFetchingNextPage}
        onClick={() => list.fetchNextPage()}
      />
    </Card>
  );
}

export default function BillingPage() {
  const overview = useQuery({
    queryKey: ['admin', 'billing', 'overview'],
    queryFn: () => api<BillingOverview>('/admin/billing'),
  });
  const data = overview.data;

  return (
    <>
      <PageHeader
        title="Payments"
        subtitle="Who has Pro, what came in, the price, and every payment. To give someone Pro or end it, open their page under Users."
      />
      {overview.isPending ? (
        <Card>
          <Loading rows={6} />
        </Card>
      ) : overview.isError || !data ? (
        <Card>
          <ErrorNote
            message={errorMessage(overview.error)}
            onRetry={() => void overview.refetch()}
          />
        </Card>
      ) : (
        <div className="space-y-6">
          {(!data.payments_enabled || !data.webhook_enabled) && (
            <Card className="p-4 ring-amber-200">
              <p className="font-semibold text-amber-900">Payments are not fully set up here</p>
              <p className="mt-1 text-sm text-zinc-700">
                {!data.payments_enabled &&
                  'Razorpay keys are missing, so nobody can pay and refunds cannot be sent. '}
                {!data.webhook_enabled &&
                  'The Razorpay webhook secret is missing, so a payment whose browser closed early only turns into Pro when the person comes back.'}
              </p>
            </Card>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Pro now"
              value={data.pro_now}
              note={`${data.paying_now} paying · ${data.granted_now} given free`}
            />
            <Metric
              label="Revenue, 30 days"
              value={formatMoney(data.revenue_30d, data.currency)}
              note={`${formatMoney(data.revenue_total, data.currency)} in all, after refunds`}
            />
            <Metric
              label="Checkouts, 30 days"
              value={`${data.paid_30d} / ${data.orders_30d}`}
              note="Paid / started. The rest closed the payment window."
            />
            <Metric
              label="Ending this week"
              value={data.expiring_7d}
              note={`Refunded so far: ${formatMoney(data.refunded_total, data.currency)}`}
            />
          </div>

          <Card>
            <h2 className="border-b border-zinc-200 px-4 py-3 font-bold">Prices</h2>
            {data.plans.length === 0 ? (
              <Empty>No plans.</Empty>
            ) : (
              <div className="divide-y divide-zinc-100">
                {data.plans.map((plan) => (
                  <PlanEditor key={`${plan.plan}-${plan.updated_at ?? ''}`} plan={plan} />
                ))}
              </div>
            )}
          </Card>

          <Orders />

          <Card>
            <h2 className="px-4 pt-4 font-bold">Changes by admins</h2>
            <p className="px-4 pb-3 text-sm text-zinc-500">
              Every refund, removal, free month and price change, with who did it and why.
            </p>
            <ActionLog actions={data.recent_actions} />
          </Card>
        </div>
      )}
    </>
  );
}
