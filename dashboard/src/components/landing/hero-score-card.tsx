'use client';

import { ArrowRight, CircleAlert, Globe, Lock } from 'lucide-react';
import Link from 'next/link';

import { type SampleSkill, tally, VERDICT_STYLE } from '@/components/landing/sample-match';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ScoreRing } from '@/features/matches/components/score-ring';
import { savePendingJob } from '@/features/preview/pending-job';
import type { JobPreview } from '@/lib/api/types';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';

const CARD =
  'bg-card text-card-foreground w-full overflow-hidden rounded-2xl border text-left shadow-2xl shadow-black/20';
const MAX_ROWS = 6;
// Rows arrive one after another; the delay is set per row.
const ROW_ENTER =
  'animate-in fade-in slide-in-from-right-2 fill-mode-both duration-500 motion-reduce:animate-none';
// Widths of the blurred bars standing in for evidence that is not known yet.
const HIDDEN_WIDTHS = ['72%', '54%', '86%', '40%', '66%', '58%'] as const;

const EXAMPLE = {
  host: 'careers.example/northwind/backend-engineer',
  title: 'Backend Engineer',
  facts: ['Northwind', 'Bengaluru', '2+ years'],
  skills: [
    { name: 'Python', required: true, verdict: 'strong', evidence: 'Built the billing service' },
    {
      name: 'PostgreSQL',
      required: true,
      verdict: 'strong',
      evidence: 'Designed the orders schema',
    },
    { name: 'REST APIs', required: true, verdict: 'strong', evidence: '14 endpoints, public docs' },
    { name: 'Docker', required: true, verdict: 'partial', evidence: 'One side project' },
    { name: 'Kubernetes', required: true, verdict: 'missing' },
    { name: 'Redis', required: false, verdict: 'missing' },
  ] satisfies SampleSkill[],
};

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function Header({
  host,
  tag,
  title,
  facts,
}: {
  host: string;
  tag: string;
  title: string;
  facts: string[];
}) {
  return (
    <>
      <div className="flex items-center gap-2.5 border-b px-5 py-3">
        <Globe className="text-muted-foreground size-3.5 shrink-0" />
        <p className="min-w-0 flex-1 truncate font-mono text-xs">{host}</p>
        <span className="text-muted-foreground shrink-0 font-mono text-[0.6875rem] tracking-wide uppercase">
          {tag}
        </span>
      </div>
      <div className="px-5 pt-4">
        <h2 className="truncate text-lg font-semibold tracking-tight">{title}</h2>
        <p className="text-muted-foreground mt-0.5 truncate text-sm">{facts.join(' · ')}</p>
      </div>
    </>
  );
}

/** A score ring with nothing readable in it: the score does not exist until there is a resume. */
function LockedRing() {
  return (
    <div className="relative size-28 shrink-0">
      <div aria-hidden className="size-full blur-[5px]">
        <svg viewBox="0 0 120 120" className="size-full -rotate-90">
          <circle
            cx="60"
            cy="60"
            r="52"
            fill="none"
            strokeWidth="10"
            className="stroke-secondary"
          />
          <circle
            cx="60"
            cy="60"
            r="52"
            fill="none"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray="327"
            strokeDashoffset="98"
            className="stroke-primary"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center gap-1.5">
          <span className="bg-foreground/70 h-9 w-5 rounded-md" />
          <span className="bg-foreground/70 h-9 w-5 rounded-md" />
        </div>
      </div>
      <span className="bg-card absolute top-1/2 left-1/2 flex size-10 -translate-1/2 items-center justify-center rounded-full border shadow-md">
        <Lock className="text-primary size-4" />
        <span className="sr-only">Your score is locked until you add your resume</span>
      </span>
    </div>
  );
}

/** Shown before any link is pasted: what a finished check looks like. */
export function ExampleScoreCard() {
  const { score } = tally(EXAMPLE.skills);
  return (
    <div className={CARD}>
      <Header host={EXAMPLE.host} tag="Example" title={EXAMPLE.title} facts={EXAMPLE.facts} />
      <div className="flex items-center gap-5 px-5 py-4">
        <ScoreRing score={score} className="size-28" draw />
        <ul className="min-w-0 flex-1">
          {EXAMPLE.skills.map((skill, index) => {
            const style = VERDICT_STYLE[skill.verdict];
            return (
              <li
                key={skill.name}
                style={{ animationDelay: `${450 + index * 90}ms` }}
                className={cn('flex items-center gap-2.5 py-1.5', ROW_ENTER)}
              >
                <span className={cn('size-1.5 shrink-0 rounded-full', style.dot)} />
                <p className="w-24 shrink-0 truncate text-sm font-medium">{skill.name}</p>
                <p className="text-muted-foreground hidden min-w-0 flex-1 truncate text-xs sm:block">
                  {skill.evidence ?? 'Not in the resume'}
                </p>
                <span className={cn('ml-auto shrink-0 font-mono text-xs', style.text)}>
                  {skill.verdict}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <p className="bg-muted/60 text-muted-foreground border-t px-5 py-3 text-xs">
        An example of the result. Paste a job link to see a real job here.
      </p>
    </div>
  );
}

export function LoadingScoreCard() {
  return (
    <div className={CARD} role="status" aria-live="polite">
      <div className="border-b px-5 py-3">
        <p className="text-sm font-medium">Reading the job page…</p>
        <p className="text-muted-foreground mt-0.5 text-xs">
          Most pages take a few seconds. Sites that block readers can take up to half a minute.
        </p>
      </div>
      <div className="px-5 pt-4">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="mt-2 h-4 w-1/2" />
      </div>
      <div className="flex items-center gap-5 px-5 py-4">
        <Skeleton className="size-28 shrink-0 rounded-full" />
        <div className="flex-1 space-y-3">
          {HIDDEN_WIDTHS.map((width) => (
            <Skeleton key={width} className="h-4" style={{ width }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ErrorScoreCard({ message, url }: { message: string; url: string }) {
  const { user } = useAuth();
  return (
    <div className={cn(CARD, 'p-6')} role="alert">
      <span className="bg-destructive/10 text-destructive flex size-10 items-center justify-center rounded-full">
        <CircleAlert className="size-5" />
      </span>
      <p className="mt-4 font-semibold">We could not read that job</p>
      <p className="text-muted-foreground mt-1 text-sm">{message}</p>
      <Button
        nativeButton={false}
        render={<Link href={user ? '/app/check' : '/login'} />}
        onClick={() => savePendingJob(url)}
        variant="outline"
        className="mt-5"
      >
        {user ? 'Paste the description instead' : 'Sign in to paste the description'}
        <ArrowRight />
      </Button>
    </div>
  );
}

/**
 * The job as we read it. Its skills are real; the score and the verdict on each
 * skill are blurred shapes, not hidden values, because they need a resume.
 */
export function LockedScoreCard({ job }: { job: JobPreview }) {
  const { user } = useAuth();
  const skills = [...job.required_skills, ...job.nice_to_have_skills];
  const shown = skills.slice(0, MAX_ROWS);
  const years = job.min_years_experience;
  const facts = [
    job.company,
    job.location,
    job.salary,
    years ? `${years}+ ${years === 1 ? 'year' : 'years'}` : null,
  ].filter((fact): fact is string => !!fact);

  return (
    <div
      className={cn(CARD, 'animate-in fade-in zoom-in-95 duration-300 motion-reduce:animate-none')}
      aria-live="polite"
    >
      <Header
        host={hostOf(job.url)}
        tag="Read from the page"
        title={job.title ?? 'Job posting'}
        facts={facts}
      />
      <div className="flex items-center gap-5 px-5 py-4">
        <LockedRing />
        {shown.length > 0 ? (
          <ul className="min-w-0 flex-1" aria-label="Skills this job asks for">
            {shown.map((skill, index) => (
              <li
                key={skill}
                style={{ animationDelay: `${index * 70}ms` }}
                className={cn('flex items-center gap-2.5 py-1.5', ROW_ENTER)}
              >
                <span className="bg-primary size-1.5 shrink-0 rounded-full" />
                <p className="w-28 shrink-0 truncate text-sm font-medium sm:w-32">{skill}</p>
                <span aria-hidden className="hidden min-w-0 flex-1 blur-[3px] sm:block">
                  <span
                    className="bg-muted-foreground/40 block h-2.5 rounded-full"
                    style={{ width: HIDDEN_WIDTHS[index % HIDDEN_WIDTHS.length] }}
                  />
                </span>
                <span
                  aria-hidden
                  className="bg-muted-foreground/40 ml-auto h-4 w-12 shrink-0 rounded-full blur-[3px]"
                />
              </li>
            ))}
            {skills.length > shown.length ? (
              <li className="text-muted-foreground pt-1.5 text-xs">
                and {skills.length - shown.length} more
              </li>
            ) : null}
          </ul>
        ) : (
          <p className="text-muted-foreground min-w-0 flex-1 text-sm">
            We read the job. Its skills are checked against your resume in the next step.
          </p>
        )}
      </div>
      <div className="bg-primary/5 flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center">
        <p className="min-w-0 flex-1 text-sm">
          <span className="font-medium">
            {skills.length > 0
              ? `This job asks for ${skills.length} ${skills.length === 1 ? 'skill' : 'skills'}.`
              : 'Your score needs your resume.'}
          </span>{' '}
          <span className="text-muted-foreground">
            {user
              ? 'See how many you match, with the evidence for each.'
              : 'Sign in and add your resume to see how many you match.'}
          </span>
        </p>
        <Button
          nativeButton={false}
          render={<Link href={user ? '/app/check' : '/login'} />}
          onClick={() => savePendingJob(job.url)}
          className="h-11 shrink-0 px-5"
        >
          Unlock my score
          <ArrowRight />
        </Button>
      </div>
    </div>
  );
}
