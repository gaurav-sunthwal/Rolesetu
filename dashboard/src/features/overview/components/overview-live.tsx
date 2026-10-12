'use client';

import { useQuery } from '@tanstack/react-query';
import { Check, ChevronRight } from 'lucide-react';
import Link from 'next/link';

import { StatusBadge } from '@/features/applications/components/status-badge';
import { useApplicationStats, useRecentApplications } from '@/features/applications/hooks';
import { useRecentMatches } from '@/features/matches/hooks';
import { useProfile } from '@/features/profile/hooks';
import { getExtensionStatus } from '@/features/settings/api';
import { errorMessage } from '@/lib/api/client';

const LABEL = 'text-muted-foreground font-mono text-[0.6875rem] tracking-[0.14em] uppercase';

/** "Get set up": steps tick off from real account data. */
export function SetupSteps() {
  const profile = useProfile();
  const matches = useRecentMatches(1);
  const extension = useQuery({ queryKey: ['extension', 'status'], queryFn: getExtensionStatus });
  const steps = [
    {
      title: 'Build your profile',
      body: 'Upload your resume to fill it in, or add your details yourself.',
      href: '/app/profile',
      done: (profile.data?.completeness ?? 0) >= 45,
    },
    {
      title: 'Check your first job',
      body: 'Paste a job description to see your match score.',
      href: '/app/check',
      done: (matches.data?.items.length ?? 0) > 0,
    },
    {
      title: 'Connect the browser extension',
      body: 'See your score on job pages as you browse.',
      href: '/app/settings',
      done: extension.data?.connected === true,
    },
    {
      title: 'Connect Gmail',
      body: 'Replies and rejections update your tracker for you.',
      href: null,
      done: false,
    },
  ];
  const loading = profile.isPending || matches.isPending;
  const done = steps.filter((step) => step.done).length;

  return (
    <section className="lg:col-span-3">
      <div className="flex items-baseline justify-between border-b pb-4">
        <h3 className="text-lg font-medium tracking-tight">Get set up</h3>
        <p className={LABEL}>{loading ? 'Checking' : `${done} of ${steps.length} done`}</p>
      </div>
      <ol>
        {steps.map((step, index) => {
          const content = (
            <>
              <span className="text-muted-foreground/60 flex h-5 w-8 shrink-0 items-center font-mono text-sm">
                {step.done ? (
                  <Check className="text-success size-4" aria-label="Done" />
                ) : (
                  `0${index + 1}`
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{step.title}</span>
                <span className="text-muted-foreground mt-0.5 block text-sm">{step.body}</span>
              </span>
              {step.href ? (
                <ChevronRight className="text-muted-foreground size-4 shrink-0 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
              ) : (
                <span className={`${LABEL} shrink-0`}>Soon</span>
              )}
            </>
          );
          const rowClass = 'flex items-start gap-3 py-4';
          return (
            <li key={step.title} className="border-b">
              {step.href ? (
                <Link
                  href={step.href}
                  className={`${rowClass} group hover:bg-muted/60 -mx-3 rounded-lg px-3 transition-colors`}
                >
                  {content}
                </Link>
              ) : (
                <div className={rowClass}>{content}</div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** "Your numbers": live figures from the application tracker. */
export function NumbersGrid() {
  const stats = useApplicationStats();
  const data = stats.data;
  const cells = [
    { label: 'Applications sent', value: data ? String(data.sent) : null },
    {
      label: 'Reply rate',
      value: data
        ? data.reply_rate === null
          ? '—'
          : `${Math.round(data.reply_rate * 100)}%`
        : null,
    },
    { label: 'Interviews', value: data ? String(data.interviews) : null },
    { label: 'Rejections', value: data ? String(data.rejections) : null },
  ];

  return (
    <section className="lg:col-span-2">
      <div className="border-b pb-4">
        <h3 className="text-lg font-medium tracking-tight">Your numbers</h3>
      </div>
      <dl className="bg-border mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-xl border">
        {cells.map((cell) => (
          <div key={cell.label} className="bg-background flex flex-col gap-6 p-4">
            <dt className={LABEL}>{cell.label}</dt>
            <dd className="text-3xl leading-none font-medium tracking-[-0.03em] tabular-nums">
              {cell.value ?? <span className="text-muted-foreground/40">·</span>}
            </dd>
          </div>
        ))}
      </dl>
      {stats.isError ? (
        <p role="alert" className="text-destructive mt-3 text-sm">
          {errorMessage(stats.error)}{' '}
          <button type="button" className="font-medium underline" onClick={() => stats.refetch()}>
            Try again
          </button>
        </p>
      ) : data && data.follow_ups_due > 0 ? (
        <Link
          href="/app/applications"
          className="mt-3 block text-sm font-medium underline-offset-4 hover:underline"
        >
          {data.follow_ups_due} waiting over a week. Time to follow up.
        </Link>
      ) : (
        <p className="text-muted-foreground mt-3 text-sm">
          {data && data.total > 0
            ? 'Reply rate counts any response, including rejections.'
            : 'These fill in as you track applications.'}
        </p>
      )}
    </section>
  );
}

/** Latest tracked jobs. Renders nothing until there is at least one. */
export function RecentApplicationsList() {
  const recent = useRecentApplications(5);
  if (!recent.data || recent.data.items.length === 0) return null;

  return (
    <section>
      <div className="flex items-baseline justify-between border-b pb-4">
        <h3 className="text-lg font-medium tracking-tight">Recent applications</h3>
        <Link
          href="/app/applications"
          className={`${LABEL} hover:text-foreground transition-colors`}
        >
          View all
        </Link>
      </div>
      <ul>
        {recent.data.items.map((application) => (
          <li key={application.id} className="flex items-center gap-3 border-b py-4">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{application.role}</span>
              <span className="text-muted-foreground mt-0.5 block truncate text-sm">
                {application.company}
              </span>
            </span>
            <StatusBadge status={application.status} />
          </li>
        ))}
      </ul>
    </section>
  );
}
