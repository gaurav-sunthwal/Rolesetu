'use client';

import {
  ArrowRight,
  FileText,
  Inbox,
  ListChecks,
  MessageSquare,
  MousePointerClick,
  PanelTop,
  Target,
} from 'lucide-react';
import { useState, type ComponentType, type ReactNode } from 'react';

import { Texture } from '@/components/brand/primitives';
import { cn } from '@/lib/utils';

const MONO = 'font-mono text-xs';

const EVIDENCE = [
  {
    skill: 'TypeScript',
    quote: 'Migrated the payments service from JavaScript',
    verdict: 'strong',
  },
  { skill: 'PostgreSQL', quote: 'Designed the orders schema', verdict: 'strong' },
  { skill: 'Node.js', quote: 'One internal CLI tool', verdict: 'partial' },
  { skill: 'Docker', quote: 'No evidence in your profile', verdict: 'missing' },
] as const;

const VERDICT_TEXT = {
  strong: 'text-success',
  partial: 'text-warning',
  missing: 'text-destructive',
} as const;

function ScorePanel() {
  return (
    <ul>
      {EVIDENCE.map((row) => (
        <li key={row.skill} className="grid grid-cols-[6rem_1fr_auto] items-baseline gap-3 py-2.5">
          <span className="text-sm font-medium">{row.skill}</span>
          <span className="text-muted-foreground truncate text-sm">“{row.quote}”</span>
          <span className={cn(MONO, VERDICT_TEXT[row.verdict])}>{row.verdict}</span>
        </li>
      ))}
    </ul>
  );
}

function OnPagePanel() {
  return (
    <div>
      <p className="text-base font-medium">Frontend Engineer</p>
      <p className="text-muted-foreground mt-0.5 text-sm">Acme Labs · Remote · Full-time</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span className="bg-foreground text-background rounded-md px-4 py-2 text-sm font-medium">
          Apply now
        </span>
        <span className="border-primary/50 bg-primary/15 flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium">
          <span className="bg-primary size-2 rounded-full" />
          67% match · Worth a shot
        </span>
      </div>
      <div className="mt-4 space-y-2" aria-hidden>
        <span className="bg-muted block h-2 w-full rounded-full" />
        <span className="bg-muted block h-2 w-4/5 rounded-full" />
        <span className="bg-muted block h-2 w-3/5 rounded-full" />
      </div>
      <p className={cn(MONO, 'text-muted-foreground mt-4 border-t pt-4')}>
        click the score for the skill-by-skill breakdown
      </p>
    </div>
  );
}

const FORM_FIELDS = [
  { label: 'Full name', value: 'Priya Sharma' },
  { label: 'Email', value: 'priya@example.com' },
  { label: 'Notice period', value: '30 days' },
  { label: 'Work authorisation', value: 'Yes' },
] as const;

function AutofillPanel() {
  return (
    <div>
      <dl className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
        {FORM_FIELDS.map((field) => (
          <div key={field.label}>
            <dt className="text-muted-foreground text-xs">{field.label}</dt>
            <dd className="border-primary/40 bg-primary/10 mt-1 flex items-center justify-between rounded-md border px-3 py-2 text-sm">
              {field.value}
              <span className={cn(MONO, 'text-primary')}>filled</span>
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex items-center justify-between border-t pt-4">
        <span className={cn(MONO, 'text-muted-foreground')}>waiting for you</span>
        <span className="bg-foreground text-background rounded-full px-4 py-1.5 text-sm font-medium">
          Submit application
        </span>
      </div>
    </div>
  );
}

const RESUME_CHANGES = [
  { kind: 'Added', before: null, after: 'Next.js', note: 'Frameworks row' },
  { kind: 'Respelled', before: 'Postgres', after: 'PostgreSQL', note: "the job's wording" },
  { kind: 'Headline', before: 'Software Engineer', after: 'Frontend Engineer', note: null },
] as const;

function ResumePanel() {
  return (
    <div>
      <ul className="space-y-1">
        {RESUME_CHANGES.map((change) => (
          <li
            key={change.after}
            className="bg-success/12 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 rounded-md px-3 py-2 text-sm"
          >
            <span className={cn(MONO, 'text-success w-20 shrink-0')}>{change.kind}</span>
            {change.before ? (
              <>
                <span className="text-muted-foreground line-through">{change.before}</span>
                <ArrowRight className="text-muted-foreground size-3.5 self-center" />
              </>
            ) : null}
            <span className="font-medium">{change.after}</span>
            {change.note ? (
              <span className="text-muted-foreground ml-auto text-xs">{change.note}</span>
            ) : null}
          </li>
        ))}
        <li className="text-muted-foreground flex flex-wrap items-baseline gap-x-2 px-3 py-2 text-sm">
          <span className={cn(MONO, 'w-20 shrink-0')}>Left out</span>
          <span className="line-through">Docker</span>
          <span className="ml-auto text-xs">you did not tick it</span>
        </li>
      </ul>
      <p className={cn(MONO, 'text-muted-foreground mt-4 border-t pt-4')}>
        same fonts · same layout · your original file
      </p>
    </div>
  );
}

const APPLICATIONS = [
  {
    company: 'Acme Labs',
    role: 'Frontend Engineer',
    status: 'Interview',
    dot: 'bg-primary',
    age: '2d',
  },
  {
    company: 'Initech',
    role: 'React Developer',
    status: 'Replied',
    dot: 'bg-warning',
    age: '4d',
  },
  {
    company: 'Northwind',
    role: 'Frontend Engineer',
    status: 'Applied',
    dot: 'bg-muted-foreground',
    age: '9d',
  },
  {
    company: 'Globex',
    role: 'UI Engineer',
    status: 'Saved',
    dot: 'bg-muted-foreground/50',
    age: '1d',
  },
] as const;

function TrackerPanel() {
  return (
    <div>
      <ul>
        {APPLICATIONS.map((row) => (
          <li
            key={row.company}
            className="grid grid-cols-[1fr_auto_2rem] items-center gap-3 border-b py-2.5 last:border-b-0"
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{row.company}</span>
              <span className="text-muted-foreground block truncate text-xs">{row.role}</span>
            </span>
            <span className="flex items-center gap-2 text-sm">
              <span className={cn('size-1.5 rounded-full', row.dot)} />
              {row.status}
            </span>
            <span className={cn(MONO, 'text-muted-foreground text-right')}>{row.age}</span>
          </li>
        ))}
      </ul>
      <p className={cn(MONO, 'text-muted-foreground mt-2 border-t pt-4')}>
        saved on apply · marked applied when the site confirms
      </p>
    </div>
  );
}

function InboxPanel() {
  return (
    <div>
      <div className="rounded-md border px-3 py-2.5">
        <p className="flex items-baseline justify-between gap-3 text-sm font-medium">
          Acme Labs Recruiting
          <span className={cn(MONO, 'text-muted-foreground font-normal')}>09:14</span>
        </p>
        <p className="text-muted-foreground mt-0.5 truncate text-sm">
          Interview availability next week
        </p>
      </div>
      <p className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Frontend Engineer</span>
        <span className="text-muted-foreground line-through">Applied</span>
        <ArrowRight className="text-muted-foreground size-3.5" />
        <span className="flex items-center gap-2 font-medium">
          <span className="bg-primary size-1.5 rounded-full" />
          Interview
        </span>
      </p>
      <p className={cn(MONO, 'text-muted-foreground mt-4 border-t pt-4')}>
        stored: sender · subject · date
      </p>
    </div>
  );
}

const WAITING = [
  { company: 'Northwind', days: 9 },
  { company: 'Hooli', days: 8 },
] as const;

function ClaudePanel() {
  return (
    <div className="space-y-3 text-sm">
      <p className="bg-primary text-primary-foreground ml-auto w-fit rounded-lg rounded-br-sm px-3 py-2">
        Who hasn&apos;t replied this week?
      </p>
      <div className="bg-muted w-fit max-w-full rounded-lg rounded-bl-sm px-3 py-2.5">
        <p className="text-muted-foreground">Two applications are still waiting:</p>
        <ul className="mt-2 space-y-1">
          {WAITING.map((item) => (
            <li key={item.company} className="flex items-baseline justify-between gap-10">
              {item.company}
              <span className={cn(MONO, 'text-muted-foreground')}>{item.days} days</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

type Feature = {
  id: string;
  icon: ComponentType<{ className?: string }>;
  title: string;
  body: string;
  windowTitle: string;
  meta: string;
  panel: ReactNode;
  /** Announced but not available yet. */
  soon?: boolean;
};

const FEATURES: Feature[] = [
  {
    id: 'score',
    icon: Target,
    title: 'Match score',
    body: 'Every skill judged against your experience, with the line that proves it.',
    windowTitle: 'match / frontend-engineer',
    meta: '67 / 100',
    panel: <ScorePanel />,
  },
  {
    id: 'on-page',
    icon: PanelTop,
    title: 'Score on the job page',
    body: 'The extension puts your score beside the Apply button on any job site.',
    windowTitle: 'acme-labs.example / careers',
    meta: 'extension',
    panel: <OnPagePanel />,
  },
  {
    id: 'tailor',
    icon: FileText,
    title: 'Resume match',
    body: 'Adds the skills you tick to your own PDF. Fonts and layout stay exactly as they were.',
    windowTitle: 'resume / acme-labs',
    meta: '3 changes',
    panel: <ResumePanel />,
  },
  {
    id: 'autofill',
    icon: MousePointerClick,
    title: 'Autofill',
    body: 'Fills empty fields from your profile and saved answers. You review and press submit.',
    windowTitle: 'application form',
    meta: '4 of 4 fields',
    panel: <AutofillPanel />,
  },
  {
    id: 'tracker',
    icon: ListChecks,
    title: 'Application tracker',
    body: 'Jobs are saved when you press Apply and marked applied when the site confirms it.',
    windowTitle: 'applications',
    meta: '4 tracked',
    panel: <TrackerPanel />,
  },
  {
    id: 'inbox',
    icon: Inbox,
    title: 'Inbox updates',
    body: 'Read-only Gmail access moves a status when a recruiter replies.',
    windowTitle: 'gmail sync',
    meta: 'coming soon',
    panel: <InboxPanel />,
    soon: true,
  },
  {
    id: 'claude',
    icon: MessageSquare,
    title: 'Ask Claude',
    body: 'Connect Rolesetu to Claude and ask about your job hunt in plain language.',
    windowTitle: 'claude',
    meta: 'coming soon',
    panel: <ClaudePanel />,
    soon: true,
  },
];

export function FeatureShowcase() {
  const [activeId, setActiveId] = useState(FEATURES[0].id);
  const active = FEATURES.find((feature) => feature.id === activeId) ?? FEATURES[0];

  return (
    <div className="bg-muted grid overflow-hidden rounded-2xl border lg:grid-cols-[21rem_1fr]">
      <div
        role="tablist"
        aria-label="Features"
        aria-orientation="vertical"
        className="flex gap-1 overflow-x-auto p-2 lg:flex-col lg:overflow-visible"
      >
        {FEATURES.map((feature) => {
          const selected = feature.id === active.id;
          return (
            <button
              key={feature.id}
              type="button"
              role="tab"
              id={`feature-tab-${feature.id}`}
              aria-selected={selected}
              aria-controls="feature-panel"
              onClick={() => setActiveId(feature.id)}
              className={cn(
                'focus-visible:ring-ring/60 flex shrink-0 items-start gap-3 rounded-xl px-3.5 py-3 text-left transition-colors outline-none focus-visible:ring-2',
                selected ? 'bg-card shadow-sm' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <feature.icon className="mt-0.5 size-4 shrink-0" />
              <span>
                <span className="text-foreground flex items-center gap-2 text-sm font-medium whitespace-nowrap">
                  {feature.title}
                  {feature.soon ? (
                    <span className={cn(MONO, 'text-muted-foreground rounded-full border px-1.5')}>
                      soon
                    </span>
                  ) : null}
                </span>
                <span
                  className={cn(
                    'mt-1 hidden text-xs leading-5 lg:block',
                    selected ? 'text-muted-foreground' : 'opacity-80',
                  )}
                >
                  {feature.body}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div
        id="feature-panel"
        role="tabpanel"
        aria-labelledby={`feature-tab-${active.id}`}
        className="relative isolate flex min-h-[26rem] items-center justify-center overflow-hidden bg-[oklch(0.42_0.22_268)] p-5 sm:p-10 lg:min-h-[31rem]"
      >
        <Texture className="-z-10 opacity-30" />
        <div className="dark bg-background text-foreground w-full max-w-xl overflow-hidden rounded-xl border shadow-2xl shadow-black/40">
          <div className="flex items-center gap-3 border-b px-4 py-3">
            <active.icon className="text-muted-foreground size-3.5 shrink-0" />
            <p className={cn(MONO, 'min-w-0 flex-1 truncate')}>{active.windowTitle}</p>
            <span className={cn(MONO, 'text-muted-foreground shrink-0')}>{active.meta}</span>
          </div>
          <div className="p-4 sm:p-5">{active.panel}</div>
        </div>
        <p className="sr-only">
          {active.body}
          {active.soon ? ' Coming soon.' : ''}
        </p>
      </div>
    </div>
  );
}
