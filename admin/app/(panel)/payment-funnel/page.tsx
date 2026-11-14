'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { Badge, Card, Empty, ErrorNote, Loading, PageHeader, pill, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime, timeAgo } from '@/lib/format';
import type { DroppedUser, FunnelEvent, PaymentFunnel } from '@/lib/types';

const PERIODS = [
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
] as const;

// What each recorded step means, in words.
const STEP_NAMES: Record<string, string> = {
  plan_viewed: 'Saw the plan page',
  upgrade_clicked: 'Clicked start autopay',
  one_time_chosen: 'Chose to pay one month',
  checkout_opened: 'Opened the payment window',
  checkout_closed: 'Closed the payment window',
  payment_failed: 'Payment failed',
  payment_succeeded: 'Paid in the window',
  verify_failed: 'Could not confirm payment',
  start_failed: 'Could not start (Razorpay down)',
  order_created: 'One-month order made',
  autopay_created: 'Autopay mandate made',
  autopay_verified: 'Autopay approved',
  charge_recorded: 'Pro turned on (charged)',
  autopay_charged: 'Autopay charged (Razorpay)',
  autopay_pending: 'Autopay retrying a failed charge',
  autopay_halted: 'Autopay stopped after failures',
  autopay_cancelled: 'Autopay cancelled (Razorpay)',
  autopay_completed: 'Autopay finished',
  autopay_cancel_asked: 'User cancelled autopay',
  autopay_stopped: 'Autopay stopped by admin or deletion',
};
const nameOf = (step: string) => STEP_NAMES[step] ?? step;
const n = (value: number) => value.toLocaleString();
const pct = (part: number, whole: number) =>
  whole > 0 ? `${Math.round((part * 100) / whole)}%` : '–';

export default function PaymentFunnelPage() {
  const [days, setDays] = useState(30);
  const query = useQuery({
    queryKey: ['payment-funnel', days],
    queryFn: () => api<PaymentFunnel>(`/admin/billing/funnel?days=${days}`),
  });

  return (
    <>
      <PageHeader
        title="Payment funnel"
        subtitle="Every step people take toward paying, why payments fail, and who left halfway."
      >
        <div className="flex flex-wrap gap-2" role="group" aria-label="Period">
          {PERIODS.map((period) => (
            <button
              key={period.days}
              className={pill(days === period.days)}
              aria-pressed={days === period.days}
              onClick={() => setDays(period.days)}
            >
              {period.label}
            </button>
          ))}
        </div>
      </PageHeader>
      {query.isPending ? (
        <Card>
          <Loading rows={8} />
        </Card>
      ) : query.isError ? (
        <Card>
          <ErrorNote message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
        </Card>
      ) : (
        <Funnel data={query.data} />
      )}
    </>
  );
}

function Funnel({ data }: { data: PaymentFunnel }) {
  const top = data.steps[0]?.users ?? 0;
  return (
    <div className="space-y-6">
      <Card className="p-5">
        <h2 className="font-bold">Steps</h2>
        <p className="text-sm text-zinc-500">People who reached each step at least once.</p>
        <ol className="mt-4 space-y-3">
          {data.steps.map((step, index) => {
            const previous = index > 0 ? (data.steps[index - 1]?.users ?? 0) : step.users;
            return (
              <li
                key={step.step}
                className="grid grid-cols-[12rem_1fr_9rem] items-center gap-3 text-sm"
              >
                <span className="font-medium">{step.label}</span>
                <span className="h-3 overflow-hidden rounded-full bg-zinc-100">
                  <span
                    className="block h-full rounded-full bg-sky-500"
                    style={{ width: `${top ? Math.max(2, (step.users / top) * 100) : 0}%` }}
                  />
                </span>
                <span className="text-right tabular-nums">
                  <strong>{n(step.users)}</strong>
                  {index > 0 ? (
                    <span className="text-zinc-500">
                      {' '}
                      · {pct(step.users, previous)} of previous
                    </span>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ol>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="px-4 pt-4 font-bold">Why payments failed</h2>
          <p className="px-4 pb-3 text-sm text-zinc-500">
            Razorpay&rsquo;s own reason where it gave one.
          </p>
          {data.failures.length === 0 ? (
            <Empty>No failed payments in this period.</Empty>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-t border-zinc-100">
                <tr>
                  <th className={th}>Reason</th>
                  <th className={th}>Where</th>
                  <th className={`${th} text-right`}>Times</th>
                  <th className={`${th} text-right`}>People</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {data.failures.map((failure) => (
                  <tr key={`${failure.step}-${failure.reason}`}>
                    <td className={`${td} max-w-xs`}>{failure.reason}</td>
                    <td className={`${td} text-zinc-500`}>{nameOf(failure.step)}</td>
                    <td className={`${td} text-right tabular-nums`}>{n(failure.count)}</td>
                    <td className={`${td} text-right tabular-nums`}>{n(failure.users)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="font-bold">Autopay</h2>
          <p className="text-sm text-zinc-500">What Razorpay reported, in people.</p>
          <dl className="mt-3 grid grid-cols-2 gap-2">
            {Object.entries(data.autopay).map(([step, count]) => (
              <div key={step} className="rounded-lg bg-zinc-50 px-3 py-2">
                <dt className="text-xs text-zinc-500">{nameOf(step)}</dt>
                <dd className="text-lg font-bold tabular-nums">{n(count)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <Card>
        <h2 className="px-4 pt-4 font-bold">Left halfway</h2>
        <p className="px-4 pb-3 text-sm text-zinc-500">
          Started paying and never finished. Open a row for the whole story. Each gets one reminder
          email an hour later.
        </p>
        {data.dropped.length === 0 ? (
          <Empty>Nobody left halfway in this period.</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100 border-t border-zinc-100">
            {data.dropped.map((user) => (
              <DroppedRow key={user.user_id} user={user} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function DroppedRow({ user }: { user: DroppedUser }) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="grid w-full gap-1 px-4 py-3 text-left text-sm hover:bg-zinc-50 md:grid-cols-[2fr_2fr_2fr_1fr] md:items-center"
      >
        <span className="min-w-0">
          <span className="block truncate font-semibold">{user.name || user.email}</span>
          <span className="block truncate text-xs text-zinc-500">{user.email}</span>
        </span>
        <span>
          {nameOf(user.last_step)}
          <span className="block text-xs text-zinc-500">{timeAgo(user.last_at)}</span>
        </span>
        <span className={user.last_error ? 'text-red-700' : 'text-zinc-400'}>
          {user.last_error ?? 'No error: they just left'}
        </span>
        <span>
          {user.reminded_at ? (
            <Badge tone="green">Reminded {timeAgo(user.reminded_at)}</Badge>
          ) : (
            <Badge>Not reminded yet</Badge>
          )}
        </span>
      </button>
      {open ? <Timeline userId={user.user_id} /> : null}
    </li>
  );
}

function Timeline({ userId }: { userId: string }) {
  const query = useQuery({
    queryKey: ['payment-timeline', userId],
    queryFn: () => api<FunnelEvent[]>(`/admin/users/${userId}/billing-funnel`),
  });
  if (query.isPending) return <Loading rows={3} />;
  if (query.isError) return <ErrorNote message={errorMessage(query.error)} />;
  return (
    <div className="bg-zinc-50/60 px-4 py-4 md:pl-8">
      <ol className="space-y-2 border-l border-zinc-200 pl-4 text-sm">
        {query.data.map((event, index) => {
          const detail = Object.entries(event.detail ?? {})
            .filter(([, value]) => value !== null && value !== '')
            .map(([key, value]) => `${key}: ${String(value)}`)
            .join(' · ');
          return (
            <li key={`${event.created_at}-${index}`}>
              <span className="font-medium">{nameOf(event.step)}</span>{' '}
              <span className="text-xs text-zinc-500">
                {formatDateTime(event.created_at)} · {event.source}
              </span>
              {detail ? <span className="block text-xs text-zinc-600">{detail}</span> : null}
            </li>
          );
        })}
      </ol>
      <Link
        href={`/users/${userId}`}
        className="mt-3 inline-block text-sm font-semibold text-sky-700 hover:underline"
      >
        Open profile →
      </Link>
    </div>
  );
}
