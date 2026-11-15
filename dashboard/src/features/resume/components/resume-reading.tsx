import { Check, FileText } from 'lucide-react';

import { cn } from '@/lib/utils';

export type ReadingStep = 'uploading' | 'reading' | 'building';

const STEPS: { key: ReadingStep; label: string }[] = [
  { key: 'uploading', label: 'Uploading your resume' },
  { key: 'reading', label: 'Reading your skills, roles and projects' },
  { key: 'building', label: 'Building your profile' },
];

/**
 * What someone sees while their resume is read: a page being scanned, and the
 * steps ticking off. Reading is quick (a second or two), so this is shown for
 * moments, not minutes; the slower AI part happens after, in the background.
 */
export function ResumeReading({
  step,
  progress = 1,
  className,
}: {
  step: ReadingStep;
  /** Upload progress, 0 to 1, while uploading. */
  progress?: number;
  className?: string;
}) {
  const current = STEPS.findIndex((item) => item.key === step);

  return (
    <section
      aria-live="polite"
      aria-busy
      className={cn('bg-card overflow-hidden rounded-3xl border p-6', className)}
    >
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
        <div className="relative isolate h-36 w-28 shrink-0 overflow-hidden rounded-xl border bg-white shadow-sm dark:bg-zinc-900">
          <div className="flex flex-col gap-2 p-3" aria-hidden>
            <span className="bg-primary/70 h-2 w-14 rounded-full" />
            <span className="bg-muted-foreground/25 h-1.5 w-20 rounded-full" />
            <span className="bg-muted-foreground/15 mt-2 h-1.5 w-full rounded-full" />
            <span className="bg-muted-foreground/15 h-1.5 w-11/12 rounded-full" />
            <span className="bg-muted-foreground/15 h-1.5 w-4/5 rounded-full" />
            <span className="bg-primary/30 mt-2 h-1.5 w-12 rounded-full" />
            <span className="bg-muted-foreground/15 h-1.5 w-full rounded-full" />
            <span className="bg-muted-foreground/15 h-1.5 w-3/4 rounded-full" />
            <span className="bg-muted-foreground/15 h-1.5 w-5/6 rounded-full" />
          </div>
          <div
            aria-hidden
            className="resume-scan from-primary/0 via-primary/25 to-primary/0 absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b"
          >
            <div className="bg-primary shadow-primary/60 absolute inset-x-0 bottom-1/2 h-0.5 shadow-[0_0_12px_2px]" />
          </div>
          <FileText
            className="text-muted-foreground/20 absolute right-2 bottom-2 size-4"
            aria-hidden
          />
        </div>

        <div className="w-full min-w-0 flex-1">
          <p className="text-lg font-semibold tracking-tight">
            {step === 'building' ? 'Almost there…' : 'Reading your resume…'}
          </p>
          <p className="text-muted-foreground text-sm">This takes a few seconds.</p>
          <ol className="mt-4 flex flex-col gap-2.5">
            {STEPS.map((item, index) => {
              const done = index < current;
              const active = index === current;
              return (
                <li
                  key={item.key}
                  className={cn(
                    'flex items-center gap-2.5 text-sm transition-colors',
                    done || active ? 'text-foreground' : 'text-muted-foreground/60',
                  )}
                >
                  <span
                    className={cn(
                      'flex size-5 shrink-0 items-center justify-center rounded-full border',
                      done && 'bg-primary border-primary text-primary-foreground',
                      active && 'border-primary',
                    )}
                    aria-hidden
                  >
                    {done ? (
                      <Check className="size-3" />
                    ) : active ? (
                      <span className="bg-primary size-2 animate-pulse rounded-full motion-reduce:animate-none" />
                    ) : null}
                  </span>
                  <span className={active ? 'font-medium' : undefined}>
                    {item.label}
                    {item.key === 'uploading' && active && progress < 1
                      ? ` · ${Math.round(progress * 100)}%`
                      : ''}
                  </span>
                  <span className="sr-only">{done ? '(done)' : active ? '(in progress)' : ''}</span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
