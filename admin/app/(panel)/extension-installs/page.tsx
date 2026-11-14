'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { ExtensionTimeline } from '@/components/ExtensionTimeline';
import { Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { InstallStats } from '@/lib/types';

const PRESETS = [
  { label: '24 h', hours: 24 },
  { label: '7 d', hours: 168 },
  { label: '30 d', hours: 720 },
  { label: '90 d', hours: 2160 },
] as const;

const REASONS: Record<string, string> = {
  no_account: 'Did not want an account',
  setup_failed: 'Could not get it set up',
  did_not_work: 'Did not work on their sites',
  not_job_hunting: 'Not job hunting now',
  privacy: 'Privacy',
  other: 'Something else',
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

function Funnel({ steps }: { steps: InstallStats['funnel'] }) {
  const first = steps[0]?.installs ?? 0;
  return (
    <ol className="space-y-3 px-4 pb-4">
      {steps.map((step, index) => (
        <li key={step.step} className="flex flex-wrap items-center gap-3 text-sm sm:flex-nowrap">
          <span className="w-64 shrink-0">
            {index + 1}. {step.label}
          </span>
          <Bar value={step.installs} max={first} />
          <span className="w-36 shrink-0 text-right text-zinc-600 tabular-nums">
            {n(step.installs)} · {pct(step.installs, first)}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Groups({ rows, label }: { rows: InstallStats['by_os']; label: string }) {
  if (rows.length === 0) return <Empty>Nothing yet.</Empty>;
  return (
    <table className="w-full text-sm">
      <thead className="border-y border-zinc-200">
        <tr>
          <th className={th}>{label}</th>
          <th className={th}>Installs</th>
          <th className={th}>Connected</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-zinc-100">
        {rows.map((row) => (
          <tr key={row.label}>
            <td className={`${td} font-medium`}>{row.label}</td>
            <td className={`${td} tabular-nums`}>{n(row.installs)}</td>
            <td className={`${td} tabular-nums`}>
              {n(row.connected)} ({pct(row.connected, row.installs)})
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Signs that an install is a machine rather than a person, in words. */
function flags(row: InstallStats['recent'][number]): string[] {
  const found: string[] = [];
  if (row.automated) found.push('automated browser');
  if (row.same_address > 0) found.push(`${row.same_address} more from this address`);
  return found;
}

function Recent({
  rows,
  selected,
  onSelect,
}: {
  rows: InstallStats['recent'];
  selected: string | null;
  onSelect: (installId: string) => void;
}) {
  if (rows.length === 0) return <Empty>No installs reported yet in this period.</Empty>;
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 border-y border-zinc-200 bg-white">
          <tr>
            <th className={th}>Installed</th>
            <th className={th}>Time zone · language</th>
            <th className={th}>System</th>
            <th className={th}>Got as far as</th>
            <th className={th}>Signs</th>
            <th className={th}>Removed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((row) => (
            <tr
              key={row.install_id}
              className={selected === row.install_id ? 'bg-blue-50' : 'hover:bg-zinc-50'}
            >
              <td className={`${td} whitespace-nowrap`}>
                <button
                  type="button"
                  className="text-left font-medium text-blue-700 hover:underline"
                  onClick={() => onSelect(row.install_id)}
                  aria-pressed={selected === row.install_id}
                >
                  {formatDateTime(row.installed_at)}
                </button>
              </td>
              <td className={td}>
                {row.timezone ?? '–'} · {row.language ?? '–'}
              </td>
              <td className={td}>
                {[row.os, row.browser, row.version && `v${row.version}`]
                  .filter(Boolean)
                  .join(' · ') || '–'}
              </td>
              <td className={td}>
                {row.user_id ? (
                  <Link href={`/users/${row.user_id}`} className="text-blue-700 hover:underline">
                    {row.reached}
                  </Link>
                ) : (
                  row.reached
                )}
              </td>
              <td className={`${td} text-amber-700`}>{flags(row).join(' · ') || '–'}</td>
              <td className={`${td} whitespace-nowrap`}>
                {row.uninstalled_at ? formatDateTime(row.uninstalled_at) : '–'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ExtensionInstallsPage() {
  const [hours, setHours] = useState<number>(720);
  const [selected, setSelected] = useState<string | null>(null);
  const stats = useQuery({
    queryKey: ['admin', 'ext-installs', hours],
    queryFn: () => api<InstallStats>('/admin/ext-installs', { params: { hours: String(hours) } }),
  });
  const data = stats.data;

  return (
    <>
      <PageHeader
        title="Installs"
        subtitle="What happens after someone installs the extension, whether or not they ever sign in. Followed by a random id per install; no names, no addresses."
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
      ) : data.installs === 0 ? (
        <Card>
          <Empty>
            No installs reported in this period. Installs are followed from the extension version
            that sends them; earlier installs only appear in the Chrome Web Store&apos;s figures.
          </Empty>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Installs"
              value={data.installs}
              note={`${n(data.uninstalled)} removed again (${pct(data.uninstalled, data.installs)})`}
            />
            <Metric
              label="Connected an account"
              value={pct(data.connected, data.installs)}
              note={`${n(data.connected)} of ${n(data.installs)}`}
            />
            <Metric
              label="Never did anything"
              value={pct(data.silent, data.installs)}
              note={`${n(data.silent)}: no setup page, no click, no job page after installing`}
            />
            <Metric
              label="Look like machines"
              value={n(Math.max(data.automated, data.crowded))}
              note={`${n(data.automated)} automated browsers · ${n(data.crowded)} from addresses with 3+ installs`}
            />
          </div>

          <Section
            title="From install to first use"
            note="Installs in this period that reached each step, and their share of all installs. The biggest drop is the step to fix."
          >
            <Funnel steps={data.funnel} />
          </Section>

          {selected && (
            <div>
              <div className="mb-2 flex justify-end">
                <button
                  type="button"
                  className="text-sm text-zinc-500 hover:underline"
                  onClick={() => setSelected(null)}
                >
                  Close journey
                </button>
              </div>
              <ExtensionTimeline installId={selected} title="This install's journey" />
            </div>
          )}

          <Section
            title="Latest installs"
            note="Click the time to see everything that install did. Many installs from one address, or an automated browser, point to a bot rather than a person."
          >
            <Recent rows={data.recent} selected={selected} onSelect={setSelected} />
          </Section>

          <div className="grid gap-6 lg:grid-cols-2">
            <Section title="Time zones" note="Where installs come from (the browser's own clock).">
              <Groups rows={data.by_timezone} label="Time zone" />
            </Section>
            <Section title="Languages" note="The browser's language.">
              <Groups rows={data.by_language} label="Language" />
            </Section>
            <Section title="Systems" note="win, mac, linux, cros (ChromeOS), android.">
              <Groups rows={data.by_os} label="System" />
            </Section>
            <Section title="Browsers" note="The browser and its version.">
              <Groups rows={data.by_browser} label="Browser" />
            </Section>
            <Section title="Extension versions" note="The version each install runs now.">
              <Groups rows={data.by_version} label="Version" />
            </Section>
            <Section
              title="Why people removed it"
              note="Answers on the page the browser opens after removing the extension (optional)."
            >
              {data.uninstall_reasons.length === 0 ? (
                <Empty>No answers yet.</Empty>
              ) : (
                <ul className="space-y-2 px-4 pb-4 text-sm">
                  {data.uninstall_reasons.map((row) => (
                    <li key={row.label} className="flex justify-between">
                      <span>{REASONS[row.label] ?? row.label}</span>
                      <span className="tabular-nums">{n(row.installs)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </div>
        </div>
      )}
    </>
  );
}
