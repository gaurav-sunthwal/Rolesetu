'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDay } from '@/lib/format';
import type { ExtAnalytics } from '@/lib/types';

const PRESETS = [
  { label: '24 h', hours: 24 },
  { label: '7 d', hours: 168 },
  { label: '30 d', hours: 720 },
  { label: '90 d', hours: 2160 },
] as const;

/** What each event means, in the words an admin reads. */
const EVENT_NAMES: Record<string, string> = {
  extension_installed: 'Installed',
  extension_updated: 'Updated',
  extension_connected: 'Connected an account',
  extension_uninstalled: 'Removed the extension',
  setup_opened: 'Setup page opened',
  setup_page_seen: 'Setup page loaded',
  signup_started: 'Started signing up',
  sign_in_failed: 'Sign-in failed',
  signed_in: 'Signed in',
  connect_failed: 'Connecting failed',
  uninstall_reason: 'Said why they removed it',
  popup_opened: 'Opened the popup',
  page_checked: 'Pressed "Check this page"',
  job_detected: 'Job page found',
  form_detected: 'Application form found',
  panel_opened: 'Opened the panel',
  job_scored: 'Job scored',
  apply_clicked: 'Clicked Apply',
  application_tracked: 'Added to tracker',
  autofill_offered: 'Autofill offered',
  autofill_filled: 'Autofill filled',
  autofill_failed: 'Autofill failed',
  autofill_undone: 'Learned answer undone',
  autofill_learned: 'Answer learned (automatic)',
  answer_saved: 'Answer saved (button)',
  suggestion_shown: 'Suggestion shown',
  suggestion_used: 'Suggestion used',
  ai_requested: 'AI asked',
  ai_succeeded: 'AI answered',
  ai_failed: 'AI failed',
  ext_error: 'Extension error',
};

const n = (value: number) => value.toLocaleString();
const pct = (part: number, whole: number) =>
  whole > 0 ? `${Math.round((part * 100) / whole)}%` : '–';

function Metric({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</p>
      <p className="mt-1 text-3xl font-bold tabular-nums">
        {typeof value === 'number' ? n(value) : value}
      </p>
      {note && <p className="mt-1 text-xs text-zinc-500">{note}</p>}
    </Card>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <h2 className="px-4 pt-4 font-bold">{title}</h2>
      <p className="px-4 pb-3 text-sm text-zinc-500">{note}</p>
      {children}
    </Card>
  );
}

function Bar({
  value,
  max,
  color = 'bg-blue-500',
}: {
  value: number;
  max: number;
  color?: string;
}) {
  const width = max > 0 ? Math.max(2, Math.round((value * 100) / max)) : 0;
  return (
    <div className="h-2 flex-1 rounded-full bg-zinc-100" aria-hidden>
      <div className={`h-2 rounded-full ${color}`} style={{ width: `${width}%` }} />
    </div>
  );
}

function Funnel({ steps }: { steps: ExtAnalytics['funnel'] }) {
  const first = steps[0]?.users ?? 0;
  if (steps.every((step) => step.users === 0))
    return <Empty>No one has reached a form yet in this period.</Empty>;
  return (
    <ol className="space-y-3 px-4 pb-4">
      {steps.map((step, index) => (
        <li key={step.step} className="flex items-center gap-3 text-sm">
          <span className="w-56 shrink-0">
            {index + 1}. {step.label}
          </span>
          <Bar value={step.users} max={first} />
          <span className="w-40 shrink-0 text-right text-zinc-600 tabular-nums">
            {n(step.users)} people · {pct(step.users, first)}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Daily({ rows }: { rows: ExtAnalytics['daily'] }) {
  if (rows.length === 0) return <Empty>No activity in this period.</Empty>;
  const top = Math.max(1, ...rows.map((row) => row.active_users));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-y border-zinc-200">
          <tr>
            <th className={th}>Day</th>
            <th className={th}>Active users</th>
            <th className={th}>Forms filled</th>
            <th className={th}>Answers saved</th>
            <th className={th}>Answers reused</th>
            <th className={th}>AI answers</th>
            <th className={th}>Jobs scored</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((row) => (
            <tr key={row.day}>
              <td className={td}>{formatDay(row.day)}</td>
              <td className={td}>
                <div className="flex items-center gap-2">
                  <Bar value={row.active_users} max={top} color="bg-zinc-800" />
                  <span className="w-8 text-right tabular-nums">{n(row.active_users)}</span>
                </div>
              </td>
              <td className={`${td} tabular-nums`}>{n(row.autofill_filled)}</td>
              <td className={`${td} tabular-nums`}>{n(row.answers_saved)}</td>
              <td className={`${td} tabular-nums`}>{n(row.suggestions_used)}</td>
              <td className={`${td} tabular-nums`}>{n(row.ai_answers)}</td>
              <td className={`${td} tabular-nums`}>{n(row.jobs_scored)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Ai({ ai }: { ai: ExtAnalytics['ai'] }) {
  if (ai.requested === 0)
    return <Empty>No one asked AI to write or improve an answer in this period.</Empty>;
  return (
    <div className="grid gap-6 px-4 pb-4 md:grid-cols-3">
      <dl className="space-y-1 text-sm">
        <div className="flex justify-between">
          <dt>Asked</dt>
          <dd className="tabular-nums">{n(ai.requested)}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Answered</dt>
          <dd className="tabular-nums">
            {n(ai.succeeded)} ({pct(ai.succeeded, ai.requested)})
          </dd>
        </div>
        <div className="flex justify-between">
          <dt>Failed</dt>
          <dd className="tabular-nums">{n(ai.failed)}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Hit the daily limit</dt>
          <dd className="tabular-nums">{n(ai.limit_hits)}</dd>
        </div>
      </dl>
      <div className="text-sm">
        <p className="mb-1 font-semibold">Why it failed</p>
        {ai.failures.length === 0 ? (
          <p className="text-zinc-500">No failures.</p>
        ) : (
          <ul className="space-y-1">
            {ai.failures.map((row) => (
              <li key={row.label} className="flex justify-between">
                <span>{row.label.replace('_', ' ')}</span>
                <span className="tabular-nums">{n(row.events)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 mb-1 font-semibold">Write or improve</p>
        <ul className="space-y-1">
          {ai.by_mode.map((row) => (
            <li key={row.label} className="flex justify-between">
              <span>{row.label}</span>
              <span className="tabular-nums">{n(row.events)}</span>
            </li>
          ))}
        </ul>
      </div>
      <dl className="space-y-1 text-sm">
        <div className="flex justify-between">
          <dt>Paid by Rolesetu</dt>
          <dd className="tabular-nums">{n(ai.paid_calls)} calls</dd>
        </div>
        <div className="flex justify-between">
          <dt>On users&apos; own keys</dt>
          <dd className="tabular-nums">{n(ai.own_key_calls)} calls</dd>
        </div>
        <div className="flex justify-between">
          <dt>Tokens in / out</dt>
          <dd className="tabular-nums">
            {n(ai.input_tokens)} / {n(ai.output_tokens)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function Sites({ rows }: { rows: ExtAnalytics['sites'] }) {
  if (rows.length === 0) return <Empty>No sites in this period.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-y border-zinc-200">
          <tr>
            <th className={th}>Site</th>
            <th className={th}>People</th>
            <th className={th}>Offered</th>
            <th className={th}>Filled</th>
            <th className={th}>Failed</th>
            <th className={th}>Fill rate</th>
            <th className={th}>Answers reused</th>
            <th className={th}>AI answers</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((row) => (
            <tr key={row.host}>
              <td className={`${td} font-medium`}>{row.host}</td>
              <td className={`${td} tabular-nums`}>{n(row.users)}</td>
              <td className={`${td} tabular-nums`}>{n(row.offered)}</td>
              <td className={`${td} tabular-nums`}>{n(row.filled)}</td>
              <td className={`${td} tabular-nums ${row.failed > 0 ? 'text-red-600' : ''}`}>
                {n(row.failed)}
              </td>
              <td className={`${td} tabular-nums`}>
                {row.offered > 0 ? `${row.fill_rate_pct}%` : '–'}
              </td>
              <td className={`${td} tabular-nums`}>{n(row.suggestions_used)}</td>
              <td className={`${td} tabular-nums`}>{n(row.ai_answers)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Features({ rows }: { rows: ExtAnalytics['features'] }) {
  if (rows.length === 0) return <Empty>No events in this period.</Empty>;
  const top = Math.max(1, ...rows.map((row) => row.events));
  return (
    <ul className="space-y-2 px-4 pb-4 text-sm">
      {rows.map((row) => (
        <li key={row.name} className="flex items-center gap-3">
          <span className="w-56 shrink-0">{EVENT_NAMES[row.name] ?? row.name}</span>
          <Bar value={row.events} max={top} color="bg-emerald-500" />
          <span className="w-44 shrink-0 text-right text-zinc-600 tabular-nums">
            {n(row.events)} times · {n(row.users)} people
          </span>
        </li>
      ))}
    </ul>
  );
}

function Versions({ rows }: { rows: ExtAnalytics['versions'] }) {
  if (rows.length === 0)
    return <Empty>No version reported yet (older versions do not send one).</Empty>;
  return (
    <ul className="space-y-1 px-4 pb-4 text-sm">
      {rows.map((row) => (
        <li key={row.version} className="flex justify-between">
          <span className="font-mono">{row.version}</span>
          <span className="tabular-nums">{n(row.users)} people</span>
        </li>
      ))}
    </ul>
  );
}

function Errors({ rows }: { rows: ExtAnalytics['errors'] }) {
  if (rows.length === 0) return <Empty>No extension errors in this period.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-y border-zinc-200">
          <tr>
            <th className={th}>Where</th>
            <th className={th}>Version</th>
            <th className={th}>Times</th>
            <th className={th}>People</th>
            <th className={th}>Last seen</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((row) => (
            <tr key={`${row.where}-${row.version ?? ''}`}>
              <td className={td}>{row.where}</td>
              <td className={`${td} font-mono`}>{row.version ?? '–'}</td>
              <td className={`${td} tabular-nums`}>{n(row.events)}</td>
              <td className={`${td} tabular-nums`}>{n(row.users)}</td>
              <td className={td}>{new Date(row.last_seen).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ExtensionUsagePage() {
  const [hours, setHours] = useState<number>(168);
  const stats = useQuery({
    queryKey: ['admin', 'ext-analytics', hours],
    queryFn: () => api<ExtAnalytics>('/admin/ext-analytics', { params: { hours: String(hours) } }),
  });
  const data = stats.data;

  return (
    <>
      <PageHeader
        title="Extension usage"
        subtitle="Who uses the extension, how far they get, what AI costs, and where it breaks. Counts only: never page content or what users type."
      >
        <div className="flex gap-2" role="group" aria-label="Period">
          {PRESETS.map((preset) => (
            <button
              key={preset.hours}
              type="button"
              aria-pressed={hours === preset.hours}
              onClick={() => setHours(preset.hours)}
              className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition ${
                hours === preset.hours
                  ? 'bg-zinc-900 text-white'
                  : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </PageHeader>

      {stats.isPending ? (
        <Card>
          <Loading rows={8} />
        </Card>
      ) : stats.isError || !data ? (
        <Card>
          <ErrorNote message={errorMessage(stats.error)} onRetry={() => void stats.refetch()} />
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Active today"
              value={data.overview.active_1d}
              note="Used the extension in the last 24 h"
            />
            <Metric
              label="Active this week"
              value={data.overview.active_7d}
              note={`${n(data.overview.active_30d)} in the last 30 days`}
            />
            <Metric
              label="Installs"
              value={data.overview.installs}
              note={`${n(data.overview.connects)} connected an account in this period`}
            />
            <Metric
              label="Errors"
              value={data.overview.errors}
              note={`${n(data.overview.updates)} updates · ${n(data.overview.events)} events in all`}
            />
          </div>

          <Section
            title="From form to reused answer"
            note="People who reached each step in this period, and what share of those who found a form."
          >
            <Funnel steps={data.funnel} />
          </Section>

          <Section title="Day by day" note="Active users and what they did each day.">
            <Daily rows={data.daily} />
          </Section>

          <Section
            title="AI answers"
            note="Write and Improve with AI: how often it is asked, how it ends, and who pays for it."
          >
            <Ai ai={data.ai} />
          </Section>

          <Section
            title="Sites"
            note="Where people use the extension. A high failed count is the next site to fix."
          >
            <Sites rows={data.sites} />
          </Section>

          <div className="grid gap-6 lg:grid-cols-2">
            <Section
              title="Every feature"
              note="How often each thing happened, and by how many people."
            >
              <Features rows={data.features} />
            </Section>
            <div className="space-y-6">
              <Section title="Versions" note="Which version people used last in this period.">
                <Versions rows={data.versions} />
              </Section>
              <Section
                title="Errors"
                note="Failures in the extension's own code, by where and version."
              >
                <Errors rows={data.errors} />
              </Section>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
