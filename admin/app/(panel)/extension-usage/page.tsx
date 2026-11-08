'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { Card, Empty, ErrorNote, Loading, PageHeader, td, th } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import type { ExtEventStats } from '@/lib/types';

const PRESETS = [
  { label: '24 h', hours: 24 },
  { label: '7 d', hours: 168 },
  { label: '30 d', hours: 720 },
  { label: '90 d', hours: 2160 },
] as const;

/** Formats a large number with thousands separators. */
const n = (v: number) => v.toLocaleString();

/** A single metric tile. */
function Metric({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</p>
      <p className="mt-1 text-3xl font-bold tabular-nums">{typeof value === 'number' ? n(value) : value}</p>
      {note && <p className="mt-1 text-xs text-zinc-400">{note}</p>}
    </Card>
  );
}

/** Mini bar chart rendered as plain divs — no charting library needed. */
function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-zinc-100">
        <div className="h-2 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="w-10 text-right text-xs tabular-nums text-zinc-500">{n(value)}</span>
    </div>
  );
}

/** Daily timeline table. */
function DailyChart({ rows }: { rows: ExtEventStats['daily'] }) {
  if (rows.length === 0) return <Empty>No events yet.</Empty>;
  const maxOffered = Math.max(...rows.map((r) => r.autofill_offered), 1);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-y border-zinc-200">
          <tr>
            <th className={th}>Day</th>
            <th className={th}>Offered</th>
            <th className={th}>Filled</th>
            <th className={th}>Jobs scored</th>
            <th className={th}>Apply clicks</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {[...rows].reverse().map((row) => (
            <tr key={row.day}>
              <td className={`${td} font-mono`}>{row.day}</td>
              <td className={`${td} w-48`}>
                <MiniBar value={row.autofill_offered} max={maxOffered} color="#2f5fe0" />
              </td>
              <td className={`${td} w-48`}>
                <MiniBar value={row.autofill_filled} max={maxOffered} color="#1f9d55" />
              </td>
              <td className={td}>{n(row.job_scored)}</td>
              <td className={td}>{n(row.apply_clicked)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Top career sites table. */
function TopSites({ rows }: { rows: ExtEventStats['top_sites'] }) {
  if (rows.length === 0) return <Empty>No sites recorded yet.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-y border-zinc-200">
          <tr>
            <th className={th}>Site</th>
            <th className={th}>Autofill offered</th>
            <th className={th}>Autofill filled</th>
            <th className={th}>Fill rate</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((site) => (
            <tr key={site.host}>
              <td className={`${td} font-semibold`}>{site.host}</td>
              <td className={td}>{n(site.offered)}</td>
              <td className={td}>{n(site.filled)}</td>
              <td className={td}>
                <span
                  className={`font-semibold ${site.fill_rate_pct >= 50 ? 'text-green-700' : site.fill_rate_pct >= 25 ? 'text-amber-600' : 'text-red-600'}`}
                >
                  {site.fill_rate_pct}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ExtensionUsagePage() {
  const [hours, setHours] = useState(168);

  const stats = useQuery({
    queryKey: ['admin', 'ext-events', hours],
    queryFn: () => api<ExtEventStats>('/admin/ext-events', { params: { hours: String(hours) } }),
  });

  const t = stats.data?.totals;

  return (
    <>
      <PageHeader
        title="Extension usage"
        subtitle="What users actually do inside the extension — autofill, scoring, applying."
      />

      {/* Period picker */}
      <div className="mb-6 flex gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.hours}
            onClick={() => setHours(p.hours)}
            className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition ${
              hours === p.hours
                ? 'bg-zinc-900 text-white'
                : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {stats.isPending ? (
        <Card>
          <Loading rows={6} />
        </Card>
      ) : stats.isError ? (
        <Card>
          <ErrorNote message={errorMessage(stats.error)} onRetry={() => stats.refetch()} />
        </Card>
      ) : (
        <div className="space-y-6">
          {/* KPI tiles */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Autofill offered" value={t!.autofill_offered} note="Forms the extension could fill" />
            <Metric
              label="Autofill filled"
              value={t!.autofill_filled}
              note={`${t!.fill_rate_pct}% fill rate`}
            />
            <Metric label="Fill failed" value={t!.autofill_failed} note="Form rejected the values" />
            <Metric label="Answers learned" value={t!.autofill_learned} note="New answers saved from forms" />
            <Metric label="Jobs scored" value={t!.job_scored} note="Match scores shown to users" />
            <Metric label="Panel opened" value={t!.panel_opened} note="Users opened the side panel" />
            <Metric label="Apply clicks" value={t!.apply_clicked} note="Apply buttons detected and clicked" />
            <Metric
              label="Fill rate"
              value={`${t!.fill_rate_pct}%`}
              note="Filled ÷ offered"
            />
          </div>

          {/* Daily chart */}
          <Card>
            <h2 className="px-4 pt-4 font-bold">Daily breakdown</h2>
            <p className="px-4 pb-3 text-sm text-zinc-500">
              Autofill offered (blue) vs filled (green), jobs scored and apply clicks per day.
            </p>
            <DailyChart rows={stats.data!.daily} />
          </Card>

          {/* Top sites */}
          <Card>
            <h2 className="px-4 pt-4 font-bold">Top career sites</h2>
            <p className="px-4 pb-3 text-sm text-zinc-500">
              Where users are applying, and how often autofill succeeds there.
            </p>
            <TopSites rows={stats.data!.top_sites} />
          </Card>
        </div>
      )}
    </>
  );
}
