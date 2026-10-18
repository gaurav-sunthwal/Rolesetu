'use client';

import { CircleAlert, Sparkles } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import { cn } from '@/lib/utils';

type Ask = 'project' | 'skill' | 'stronger';

const ASKS: { id: Ask; prompt: string; reply: string }[] = [
  {
    id: 'project',
    prompt: 'Add my Rolesetu project',
    reply: 'Added Rolesetu under Projects from your profile, with its GitHub link.',
  },
  {
    id: 'skill',
    prompt: 'Put Docker in my skills',
    reply: 'Added Docker to your Tools row.',
  },
  {
    id: 'stronger',
    prompt: 'Make my Northwind bullets stronger',
    reply:
      'Reworded both bullets. I left out one change: it said “by 40%”, which you never told me.',
  },
];

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

/** The editor's assistant in miniature: ask in plain words, watch your own page change. */
export function ResumeAssistantDemo() {
  const [ask, setAsk] = useState<Ask>('project');
  const current = ASKS.find((item) => item.id === ask) ?? ASKS[0];

  return (
    <div className="w-full text-left text-white">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Sparkles className="size-4" />
          Ask the resume assistant
        </p>
        <span className="font-mono text-[0.6875rem] tracking-wide text-white/80 uppercase">
          Sample
        </span>
      </div>
      <div role="tablist" aria-label="Sample requests" className="mt-3 flex flex-wrap gap-2">
        {ASKS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`assist-tab-${item.id}`}
            aria-selected={ask === item.id}
            aria-controls="assist-demo-page"
            onClick={() => setAsk(item.id)}
            className={cn(
              'rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-white/70',
              ask === item.id
                ? 'bg-white text-neutral-900'
                : 'bg-black/25 text-white/85 hover:text-white',
            )}
          >
            {item.prompt}
          </button>
        ))}
      </div>

      <p
        className="mt-3 flex items-start gap-2 rounded-xl bg-black/25 px-3.5 py-2.5 text-sm"
        aria-live="polite"
      >
        <Sparkles className="mt-0.5 size-3.5 shrink-0" />
        <span>{current.reply}</span>
      </p>

      <div
        id="assist-demo-page"
        role="tabpanel"
        aria-labelledby={`assist-tab-${ask}`}
        className="mt-3 rounded-lg bg-white p-5 font-serif text-neutral-900 shadow-2xl shadow-black/30 sm:p-7"
      >
        <p className="text-center text-xl font-semibold tracking-tight">Priya Sharma</p>
        <p className="mt-1 text-center text-xs text-neutral-600">
          Frontend Engineer · Pune ·{' '}
          <span className="text-[oklch(0.45_0.2_263)] underline underline-offset-2">
            github.com/priya
          </span>
        </p>

        <Heading>Experience</Heading>
        <p className="mt-2 flex items-baseline justify-between gap-3 text-xs">
          <span className="font-semibold">Software Engineer, Northwind</span>
          <span className="shrink-0 text-neutral-600">2022 – Present</span>
        </p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs leading-5 text-neutral-700">
          <li>
            <Changed on={ask === 'stronger'}>
              {ask === 'stronger'
                ? 'Designed and built a 40-screen admin app now used by 3 teams'
                : 'Built a 40-screen admin app used by 3 teams'}
            </Changed>
          </li>
          <li>
            <Changed on={ask === 'stronger'}>
              {ask === 'stronger'
                ? 'Led the migration of the payments service from JavaScript to TypeScript'
                : 'Migrated the payments service from JavaScript'}
            </Changed>
          </li>
        </ul>

        <Heading>Projects</Heading>
        <p className="mt-2 text-xs">
          <span className="font-semibold">Job Tracker</span> | <i>Next.js, PostgreSQL</i>
        </p>
        <ul className="mt-1 list-disc pl-4 text-xs leading-5 text-neutral-700">
          <li>A kanban board for job applications with email reminders</li>
        </ul>
        {ask === 'project' ? (
          <div className="motion-safe:animate-in motion-safe:fade-in">
            <p className="mt-1.5 text-xs">
              <Changed on>
                <span className="font-semibold">Rolesetu</span> | <i>Next.js, FastAPI</i>
              </Changed>
            </p>
            <ul className="mt-1 list-disc pl-4 text-xs leading-5 text-neutral-700">
              <li>
                <Changed on>
                  Scores jobs against a resume ·{' '}
                  <span className="text-[oklch(0.45_0.2_263)] underline underline-offset-2">
                    github.com/priya/rolesetu
                  </span>
                </Changed>
              </li>
            </ul>
          </div>
        ) : null}

        <Heading>Skills</Heading>
        <dl className="mt-2 space-y-1 text-xs leading-5">
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 font-semibold">Languages</dt>
            <dd>TypeScript, JavaScript, SQL</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 font-semibold">Tools</dt>
            <dd>
              Git, Figma
              {ask === 'skill' ? (
                <>
                  , <Changed on>Docker</Changed>
                </>
              ) : null}
            </dd>
          </div>
        </dl>
      </div>

      {ask === 'stronger' ? (
        <p className="mt-3 flex items-start gap-2 text-sm">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span>
            <span className="font-medium">Held back:</span> “cut load time by 40%”. Nothing you
            wrote or saved says that, so it waits for you to confirm it is true.
          </span>
        </p>
      ) : null}
      <p className="mt-3 text-xs text-white/75">
        Highlighted here to show what changed. Your file keeps its own fonts, layout and links.
      </p>
    </div>
  );
}
