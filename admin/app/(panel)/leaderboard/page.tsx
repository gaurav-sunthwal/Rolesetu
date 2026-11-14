'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { Badge, Card, Empty, ErrorNote, Loading, PageHeader, pill } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDate, timeAgo } from '@/lib/format';
import type { Leaderboard, LeaderFeature, LeaderRow } from '@/lib/types';

const PERIODS = [
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: 'All time', days: null },
] as const;

// One colour per feature, so a feature looks the same in every bar and legend.
const COLORS: Record<string, string> = {
  job_check: 'bg-sky-500',
  extension_score: 'bg-emerald-500',
  autofill: 'bg-teal-400',
  suggestion_used: 'bg-lime-500',
  answer_saved: 'bg-green-700',
  ai_answer: 'bg-violet-500',
  resume_assistant: 'bg-fuchsia-500',
  application: 'bg-amber-500',
  email_tracked: 'bg-orange-400',
  share: 'bg-rose-400',
  resume_upload: 'bg-zinc-400',
};
const colorOf = (key: string) => COLORS[key] ?? 'bg-zinc-300';
const n = (value: number) => value.toLocaleString();
const MEDALS = ['🥇', '🥈', '🥉'];

export default function LeaderboardPage() {
  const [days, setDays] = useState<number | null>(30);
  const [open, setOpen] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ['leaderboard', days],
    queryFn: () => api<Leaderboard>(`/admin/leaderboard?limit=50${days ? `&days=${days}` : ''}`),
  });

  return (
    <>
      <PageHeader
        title="Leaderboard"
        subtitle="Who uses Rolesetu most, and which features they use. Counted from what each feature already records."
      >
        <div className="flex flex-wrap gap-2" role="group" aria-label="Period">
          {PERIODS.map((period) => (
            <button
              key={period.label}
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
      ) : query.data.users.length === 0 ? (
        <Card>
          <Empty>Nobody used Rolesetu in this period.</Empty>
        </Card>
      ) : (
        <Board data={query.data} open={open} onToggle={(id) => setOpen(open === id ? null : id)} />
      )}
    </>
  );
}

function Board({
  data,
  open,
  onToggle,
}: {
  data: Leaderboard;
  open: string | null;
  onToggle: (id: string) => void;
}) {
  const labels = Object.fromEntries(data.features.map((f) => [f.key, f.label]));
  const totalActions = Object.values(data.totals).reduce((sum, value) => sum + value, 0);
  const [podium, rest] = [data.users.slice(0, 3), data.users.slice(3)];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Active users" value={n(data.active_users)} />
        <Metric label="Actions" value={n(totalActions)} />
        <Metric
          label="Most used feature"
          value={(() => {
            const top = Object.entries(data.totals).sort((a, b) => b[1] - a[1])[0];
            return top ? (labels[top[0]] ?? top[0]) : '–';
          })()}
        />
      </div>

      <FeatureMix features={data.features} totals={data.totals} />

      <section aria-labelledby="top-three">
        <h2 id="top-three" className="mb-3 font-bold">
          Top users
        </h2>
        <div className="grid gap-4 lg:grid-cols-3">
          {podium.map((user) => (
            <PodiumCard key={user.user_id} user={user} labels={labels} />
          ))}
        </div>
      </section>

      {rest.length > 0 ? (
        <Card>
          <h2 className="px-4 pt-4 font-bold">Everyone else</h2>
          <p className="px-4 pb-3 text-sm text-zinc-500">
            Click a user to see every feature they used.
          </p>
          <ol className="divide-y divide-zinc-100 border-t border-zinc-100">
            {rest.map((user) => (
              <UserRow
                key={user.user_id}
                user={user}
                labels={labels}
                features={data.features}
                open={open === user.user_id}
                onToggle={() => onToggle(user.user_id)}
              />
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">{label}</p>
      <p className="mt-1 truncate text-2xl font-bold tabular-nums">{value}</p>
    </Card>
  );
}

/** What the whole user base used in the period, biggest first. */
function FeatureMix({
  features,
  totals,
}: {
  features: LeaderFeature[];
  totals: Record<string, number>;
}) {
  const used = features
    .map((feature) => ({ ...feature, count: totals[feature.key] ?? 0 }))
    .filter((feature) => feature.count > 0)
    .sort((a, b) => b.count - a.count);
  const max = used[0]?.count ?? 1;
  return (
    <Card className="p-4">
      <h2 className="font-bold">Features used by everyone</h2>
      <ul className="mt-3 space-y-2">
        {used.map((feature) => (
          <li
            key={feature.key}
            className="grid grid-cols-[10rem_1fr_4rem] items-center gap-3 text-sm"
          >
            <span className="truncate">{feature.label}</span>
            <span className="h-2.5 overflow-hidden rounded-full bg-zinc-100">
              <span
                className={`block h-full rounded-full ${colorOf(feature.key)}`}
                style={{ width: `${Math.max(2, (feature.count / max) * 100)}%` }}
              />
            </span>
            <span className="text-right font-semibold tabular-nums">{n(feature.count)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Avatar({ user, size = 'md' }: { user: LeaderRow; size?: 'md' | 'lg' }) {
  const letter = (user.name || user.email).charAt(0).toUpperCase();
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full bg-zinc-900 font-bold text-white ${size === 'lg' ? 'size-12 text-lg' : 'size-9 text-sm'}`}
    >
      {letter}
    </span>
  );
}

function Status({ user }: { user: LeaderRow }) {
  return (
    <span className="flex flex-wrap gap-1">
      {user.plan === 'pro' ? <Badge tone="blue">Pro</Badge> : <Badge>Free</Badge>}
      {user.extension_connected ? <Badge tone="green">Extension</Badge> : null}
      {user.gmail_connected ? <Badge tone="amber">Gmail</Badge> : null}
      {!user.has_resume ? <Badge tone="red">No resume</Badge> : null}
    </span>
  );
}

/** One user's features as one bar, each part sized by how much it was used. */
function MixBar({ user, labels }: { user: LeaderRow; labels: Record<string, string> }) {
  const parts = Object.entries(user.features).sort((a, b) => b[1] - a[1]);
  return (
    <span
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-zinc-100"
      role="img"
      aria-label={parts.map(([key, count]) => `${labels[key] ?? key}: ${count}`).join(', ')}
    >
      {parts.map(([key, count]) => (
        <span
          key={key}
          className={colorOf(key)}
          style={{ width: `${(count / user.total_actions) * 100}%` }}
          title={`${labels[key] ?? key}: ${n(count)}`}
        />
      ))}
    </span>
  );
}

function TopChips({ user, labels }: { user: LeaderRow; labels: Record<string, string> }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {user.top_features.map((key) => (
        <span
          key={key}
          className="inline-flex items-center gap-1.5 rounded-full bg-zinc-50 px-2 py-0.5 text-xs font-medium ring-1 ring-zinc-200"
        >
          <span className={`size-2 rounded-full ${colorOf(key)}`} aria-hidden />
          {labels[key] ?? key} · {n(user.features[key] ?? 0)}
        </span>
      ))}
    </span>
  );
}

function PodiumCard({ user, labels }: { user: LeaderRow; labels: Record<string, string> }) {
  return (
    <Card className={`flex flex-col p-5 ${user.rank === 1 ? 'ring-2 ring-amber-300' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Avatar user={user} size="lg" />
          <div className="min-w-0">
            <p className="truncate font-bold">{user.name || user.email.split('@')[0]}</p>
            <p className="truncate text-xs text-zinc-500">{user.email}</p>
          </div>
        </div>
        <span className="text-2xl" aria-label={`Rank ${user.rank}`}>
          {MEDALS[user.rank - 1] ?? `#${user.rank}`}
        </span>
      </div>
      {user.headline ? (
        <p className="mt-3 line-clamp-2 text-sm text-zinc-600">{user.headline}</p>
      ) : null}
      <div className="mt-3">
        <Status user={user} />
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <Stat label="Actions" value={n(user.total_actions)} />
        <Stat label="Active days" value={n(user.active_days)} />
        <Stat label="Last seen" value={timeAgo(user.last_active_at)} />
      </dl>
      <div className="mt-4">
        <MixBar user={user} labels={labels} />
      </div>
      <div className="mt-3">
        <TopChips user={user} labels={labels} />
      </div>
      <Link
        href={`/users/${user.user_id}`}
        className="mt-4 text-sm font-semibold text-sky-700 hover:underline"
      >
        Open profile →
      </Link>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-zinc-50 px-2 py-2">
      <dt className="text-[0.6875rem] font-semibold tracking-wide text-zinc-500 uppercase">
        {label}
      </dt>
      <dd className="mt-0.5 font-bold tabular-nums">{value}</dd>
    </div>
  );
}

function UserRow({
  user,
  labels,
  features,
  open,
  onToggle,
}: {
  user: LeaderRow;
  labels: Record<string, string>;
  features: LeaderFeature[];
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50 md:grid-cols-[2.5rem_minmax(0,2fr)_minmax(0,2fr)_6rem]"
      >
        <span className="text-center text-sm font-bold text-zinc-500 tabular-nums">
          #{user.rank}
        </span>
        <span className="flex min-w-0 items-center gap-3">
          <Avatar user={user} />
          <span className="min-w-0">
            <span className="block truncate font-semibold">
              {user.name || user.email.split('@')[0]}
            </span>
            <span className="block truncate text-xs text-zinc-500">
              {user.headline || user.email}
            </span>
          </span>
        </span>
        <span className="col-start-2 flex flex-col gap-1.5 md:col-start-auto">
          <MixBar user={user} labels={labels} />
          <TopChips user={user} labels={labels} />
        </span>
        <span className="col-start-2 text-sm md:col-start-auto md:text-right">
          <span className="font-bold tabular-nums">{n(user.total_actions)}</span>
          <span className="text-zinc-500"> actions</span>
          <span className="block text-xs text-zinc-500">{user.active_days} active days</span>
        </span>
      </button>
      {open ? <UserDetail user={user} features={features} /> : null}
    </li>
  );
}

/** Every feature for one user, used ones first, with their profile beside it. */
function UserDetail({ user, features }: { user: LeaderRow; features: LeaderFeature[] }) {
  const rows = features
    .map((feature) => ({ ...feature, count: user.features[feature.key] ?? 0 }))
    .sort((a, b) => b.count - a.count);
  const max = rows[0]?.count || 1;
  return (
    <div className="grid gap-6 bg-zinc-50/60 px-4 py-5 md:grid-cols-[1fr_2fr] md:pl-16">
      <div className="space-y-2 text-sm">
        <Status user={user} />
        <p className="text-zinc-700">{user.email}</p>
        {user.location ? <p className="text-zinc-500">{user.location}</p> : null}
        <p className="text-zinc-500">Joined {formatDate(user.joined_at)}</p>
        <p className="text-zinc-500">Last active {timeAgo(user.last_active_at)}</p>
        <Link
          href={`/users/${user.user_id}`}
          className="inline-block font-semibold text-sky-700 hover:underline"
        >
          Open profile →
        </Link>
      </div>
      <ul className="space-y-1.5">
        {rows.map((feature) => (
          <li
            key={feature.key}
            className={`grid grid-cols-[10rem_1fr_3rem] items-center gap-3 text-sm ${feature.count === 0 ? 'text-zinc-400' : ''}`}
          >
            <span className="truncate">{feature.label}</span>
            <span className="h-2 overflow-hidden rounded-full bg-zinc-100">
              {feature.count > 0 ? (
                <span
                  className={`block h-full rounded-full ${colorOf(feature.key)}`}
                  style={{ width: `${(feature.count / max) * 100}%` }}
                />
              ) : null}
            </span>
            <span className="text-right tabular-nums">
              {feature.count ? n(feature.count) : '–'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
