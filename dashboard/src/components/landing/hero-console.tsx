'use client';

import { ArrowRight, FileText, ListChecks, ScanSearch } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { useCtaHref } from '@/components/landing/landing-cta';
import { SAMPLE_JOB_URL } from '@/components/landing/sample-match';
import { cn } from '@/lib/utils';

const MODES = [
  { id: 'check', label: 'Check a job', icon: ScanSearch, action: 'Score this job' },
  { id: 'tailor', label: 'Tailor resume', icon: FileText, action: 'Tailor my resume' },
  { id: 'track', label: 'Track', icon: ListChecks, action: 'Add to tracker' },
] as const;

type ModeId = (typeof MODES)[number]['id'];

/** Everything starts from one job link: pick what to do with it, then continue into the app. */
export function HeroConsole() {
  const [active, setActive] = useState<ModeId>('check');
  const href = useCtaHref();
  const mode = MODES.find((item) => item.id === active) ?? MODES[0];

  return (
    <div className="mx-auto w-full max-w-3xl rounded-2xl border border-white/70 bg-white/55 p-3 text-left shadow-[0_20px_60px_-24px_rgb(30_58_138/0.55)] backdrop-blur-xl sm:p-3.5 dark:border-white/15 dark:bg-white/8">
      <div className="flex gap-1 overflow-x-auto">
        {MODES.map((item) => {
          const selected = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected}
              onClick={() => setActive(item.id)}
              className={cn(
                'focus-visible:ring-ring/60 flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-2',
                selected
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-foreground/60 hover:text-foreground',
              )}
            >
              <span
                className={cn(
                  'flex size-6 items-center justify-center rounded-md',
                  selected ? 'bg-primary text-primary-foreground' : 'bg-foreground/8',
                )}
              >
                <item.icon className="size-3.5" />
              </span>
              {item.label}
            </button>
          );
        })}
      </div>

      <Link
        href={href}
        className="group bg-background/75 hover:bg-background focus-visible:ring-ring/60 mt-3 flex h-14 items-center gap-3 rounded-xl pr-2 pl-5 transition-colors outline-none focus-visible:ring-2"
      >
        <span className="text-foreground/70 min-w-0 flex-1 truncate font-mono text-sm">
          {SAMPLE_JOB_URL}
        </span>
        <span className="text-foreground/60 hidden text-sm font-medium sm:inline">
          {mode.action}
        </span>
        <span className="bg-primary text-primary-foreground flex size-10 shrink-0 items-center justify-center rounded-lg shadow-sm transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none">
          <ArrowRight className="size-4" />
        </span>
        <span className="sr-only">{mode.action}</span>
      </Link>
    </div>
  );
}
