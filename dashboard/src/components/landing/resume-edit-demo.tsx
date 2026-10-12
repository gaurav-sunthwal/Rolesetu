'use client';

import { CircleCheck } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import { cn } from '@/lib/utils';

type View = 'after' | 'before';

const VIEWS = [
  { id: 'after', label: 'Updated' },
  { id: 'before', label: 'Original' },
] as const;

const CHANGES = [
  { kind: 'Headline', before: 'Software Engineer', after: 'Frontend Engineer' },
  { kind: 'Respelled', before: 'Postgres', after: 'PostgreSQL' },
  { kind: 'Added', before: null, after: 'Next.js' },
] as const;

/** Marks a changed word. The real file carries no highlight; this only shows where to look. */
function Changed({ on, children }: { on: boolean; children: ReactNode }) {
  return (
    <span
      className={cn(
        'rounded-[3px] px-0.5 transition-colors motion-reduce:transition-none',
        on && 'bg-[oklch(0.9_0.09_263)]',
      )}
    >
      {children}
    </span>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 border-b border-neutral-300 pb-1 text-[0.6875rem] font-semibold tracking-[0.12em] uppercase">
      {children}
    </p>
  );
}

/** The same before/after switch the app shows before a tailored resume is downloaded. */
export function ResumeEditDemo() {
  const [view, setView] = useState<View>('after');
  const after = view === 'after';

  return (
    <div className="w-full text-left text-white">
      <div className="flex items-center justify-between gap-3">
        <div
          role="tablist"
          aria-label="Which version to show"
          className="inline-flex rounded-full bg-black/25 p-1"
        >
          {VIEWS.map((option) => (
            <button
              key={option.id}
              type="button"
              role="tab"
              id={`resume-tab-${option.id}`}
              aria-selected={view === option.id}
              aria-controls="resume-demo-page"
              onClick={() => setView(option.id)}
              className={cn(
                'rounded-full px-4 py-1.5 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-white/70',
                view === option.id ? 'bg-white text-neutral-900' : 'text-white/80 hover:text-white',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        <span className="font-mono text-[0.6875rem] tracking-wide text-white/80 uppercase">
          Sample
        </span>
      </div>

      <div
        id="resume-demo-page"
        role="tabpanel"
        aria-labelledby={`resume-tab-${view}`}
        className="mt-4 rounded-lg bg-white p-5 font-serif text-neutral-900 shadow-2xl shadow-black/30 sm:p-7"
      >
        <p className="text-center text-xl font-semibold tracking-tight">Priya Sharma</p>
        <p className="mt-1 text-center text-xs text-neutral-600">
          <Changed on={after}>{after ? 'Frontend Engineer' : 'Software Engineer'}</Changed> · Pune ·
          priya@example.com
        </p>

        <Heading>Skills</Heading>
        <dl className="mt-2 space-y-1 text-xs leading-5">
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 font-semibold">Languages</dt>
            <dd>TypeScript, JavaScript, SQL</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 font-semibold">Frameworks</dt>
            <dd>
              React, Node.js
              {after ? (
                <>
                  , <Changed on>Next.js</Changed>
                </>
              ) : null}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 font-semibold">Databases</dt>
            <dd>
              <Changed on={after}>{after ? 'PostgreSQL' : 'Postgres'}</Changed>, Redis
            </dd>
          </div>
        </dl>

        <Heading>Experience</Heading>
        <p className="mt-2 flex items-baseline justify-between gap-3 text-xs">
          <span className="font-semibold">Software Engineer, Northwind</span>
          <span className="shrink-0 text-neutral-600">2022 – Present</span>
        </p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs leading-5 text-neutral-700">
          <li>Built a 40-screen admin app used by 3 teams</li>
          <li>Migrated the payments service from JavaScript</li>
        </ul>
      </div>

      <ul className="mt-4 space-y-1.5 text-sm">
        {CHANGES.map((change) => (
          <li key={change.after} className="flex items-start gap-2">
            <CircleCheck className="mt-0.5 size-4 shrink-0" />
            <span>
              <span className="text-white/75">{change.kind}: </span>
              {change.before ? (
                <>
                  <span className="line-through">{change.before}</span>
                  {' → '}
                </>
              ) : null}
              <span className="font-medium">{change.after}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-white/75">
        Highlighted here to show what changed. Your file has no highlights.
      </p>
    </div>
  );
}
