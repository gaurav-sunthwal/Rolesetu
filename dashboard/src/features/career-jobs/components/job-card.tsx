'use client';

import { useQueryClient } from '@tanstack/react-query';
import {
  CircleCheck,
  ExternalLink,
  Info,
  MapPin,
  ScanSearch,
  TrendingUp,
  Undo2,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { InlineError } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useCreateApplication, useDeleteApplication } from '@/features/applications/hooks';
import { ScoreBoosts } from '@/features/career-jobs/components/score-boosts';
import { careerJobKeys } from '@/features/career-jobs/hooks';
import { WORK_MODE_META } from '@/features/career-jobs/work-mode';
import { SkillGroup } from '@/features/matches/components/match-result';
import { bandOf } from '@/features/matches/score';
import { savePendingJob } from '@/features/preview/pending-job';
import { errorMessage } from '@/lib/api/client';
import type { CareerFit, CareerJob } from '@/lib/api/types';
import { timeAgo } from '@/lib/format';
import { cn } from '@/lib/utils';

const FIT_META: Record<CareerFit, { label: string; className: string }> = {
  fits: { label: 'Fits your experience', className: 'bg-success/10 text-success' },
  stretch: { label: 'Stretch: +1 year', className: 'bg-warning/15 text-foreground' },
  not_stated: { label: 'Experience not stated', className: 'bg-secondary text-muted-foreground' },
};

const CHIPS_SHOWN = 3;
// Matches the API: fewer recognised skills than this and the score ranks lower.
const WELL_EVIDENCED = 3;

function postedLabel(job: CareerJob): string {
  if (job.posted_on) return `Posted ${timeAgo(`${job.posted_on}T00:00:00`)}`;
  return `Seen ${timeAgo(`${job.first_seen}T00:00:00`)}`;
}

// "Remote" is shown as the work mode, so the place list leaves it out.
function placesLabel(job: CareerJob): string {
  return job.places.filter((place) => place !== 'Remote').join(', ');
}

function WorkModeTag({ job }: { job: CareerJob }) {
  if (job.work_mode === 'not_stated') return null;
  const meta = WORK_MODE_META[job.work_mode];
  const Icon = meta.icon;
  return (
    <span className="bg-secondary text-foreground inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium">
      {Icon ? <Icon className="size-3" /> : null}
      {meta.label}
    </span>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className="bg-secondary text-muted-foreground flex size-12 shrink-0 items-center justify-center rounded-2xl text-center text-[10px] leading-tight">
        No score
      </div>
    );
  }
  const band = bandOf(score);
  return (
    <div
      className="bg-secondary flex size-12 shrink-0 flex-col items-center justify-center rounded-2xl"
      role="img"
      aria-label={`Match score ${score} out of 100: ${band.label}`}
    >
      <span className={cn('text-lg leading-none font-bold tabular-nums', band.text)}>{score}</span>
      <span className="text-muted-foreground mt-0.5 text-[10px] leading-none">/ 100</span>
    </div>
  );
}

function SkillChips({ job }: { job: CareerJob }) {
  const have = job.skill_results.filter((s) => s.verdict !== 'missing');
  const missing = job.skill_results.filter((s) => s.verdict === 'missing' && s.required);
  if (job.skill_results.length === 0) {
    return (
      <p className="text-muted-foreground text-xs">
        No skills we recognise in this posting, so it has no score. Read it to judge yourself.
      </p>
    );
  }
  const hidden = Math.max(have.length - CHIPS_SHOWN, 0) + Math.max(missing.length - CHIPS_SHOWN, 0);
  return (
    <div className="flex flex-wrap gap-1.5 text-xs">
      {have.slice(0, CHIPS_SHOWN).map((skill) => (
        <span
          key={skill.name}
          className={cn(
            'rounded-full px-2 py-0.5',
            skill.verdict === 'strong' ? 'bg-success/10 text-success' : 'bg-warning/15',
          )}
        >
          {skill.name}
        </span>
      ))}
      {missing.slice(0, CHIPS_SHOWN).map((skill) => (
        <span
          key={skill.name}
          className="bg-destructive/10 text-destructive rounded-full px-2 py-0.5"
        >
          Missing: {skill.name}
        </span>
      ))}
      {hidden > 0 ? (
        <span className="text-muted-foreground rounded-full px-1 py-0.5">+{hidden} more</span>
      ) : null}
    </div>
  );
}

export function JobCard({ job }: { job: CareerJob }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [explaining, setExplaining] = useState(false);
  // Set once the click on Apply has been recorded in the user's applications.
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const track = useCreateApplication();
  const untrack = useDeleteApplication();
  const fit = FIT_META[job.fit];
  const thin = job.skill_results.length > 0 && job.skill_results.length < WELL_EVIDENCED;

  function checkInDetail() {
    savePendingJob(job.url);
    router.push('/app/check');
  }

  /** The link opens the company's page; this records the application alongside it. */
  function recordApply() {
    setExplaining(false);
    track.mutate(
      {
        body: {
          role: job.title.slice(0, 160),
          company: job.company.slice(0, 160),
          url: job.url,
          location: job.places.join(', ').slice(0, 160),
          status: 'applied',
        },
        // One application per job, however many times Apply is clicked.
        idempotencyKey: `career-job:${job.id}`,
      },
      {
        onSuccess: (application) => {
          setApplicationId(application.id);
          // The list leaves this job out from now on; refetched next time it is opened.
          void queryClient.invalidateQueries({
            queryKey: careerJobKeys.all,
            refetchType: 'none',
          });
        },
      },
    );
  }

  function undo() {
    if (!applicationId) return;
    untrack.mutate(applicationId, { onSuccess: () => setApplicationId(null) });
  }

  if (applicationId) {
    return (
      <li
        className="bg-card flex flex-col justify-center gap-3 rounded-3xl border border-dashed p-5"
        aria-live="polite"
      >
        <p className="flex items-center gap-2 text-sm font-semibold">
          <CircleCheck className="text-success size-4 shrink-0" />
          Added to your applications
        </p>
        <p className="text-muted-foreground text-sm">
          {job.title} at {job.company}. It won&apos;t show here again.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            nativeButton={false}
            render={<Link href="/app/applications" />}
          >
            View applications
          </Button>
          <Button size="sm" variant="ghost" onClick={undo} disabled={untrack.isPending}>
            <Undo2 />
            {untrack.isPending ? 'Undoing…' : 'Undo'}
          </Button>
        </div>
        {untrack.isError ? <InlineError>{errorMessage(untrack.error)}</InlineError> : null}
      </li>
    );
  }

  return (
    <li className="bg-card flex flex-col rounded-3xl border p-5 transition-shadow hover:shadow-md motion-reduce:transition-none">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{job.company}</p>
          <p className="text-muted-foreground text-xs">{postedLabel(job)}</p>
        </div>
        <ScoreBadge score={job.score} />
      </div>

      <h3 className="mt-3 line-clamp-2 leading-snug font-semibold">
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary underline-offset-4 hover:underline"
        >
          {job.title}
        </a>
      </h3>
      <div className="text-muted-foreground mt-1 flex min-w-0 items-center gap-2 text-sm">
        {placesLabel(job) ? (
          <span className="flex min-w-0 items-center gap-1">
            <MapPin className="size-3.5 shrink-0" />
            <span className="truncate">{placesLabel(job)}</span>
          </span>
        ) : null}
        <WorkModeTag job={job} />
      </div>

      <span
        className={cn('mt-3 w-fit rounded-full px-2.5 py-0.5 text-xs font-medium', fit.className)}
      >
        {fit.label}
      </span>

      <div className="mt-3">
        <SkillChips job={job} />
        {thin ? (
          <p className="text-muted-foreground mt-1.5 text-xs">
            Only {job.skill_results.length} {job.skill_results.length === 1 ? 'skill' : 'skills'}{' '}
            recognised, so read the posting before trusting the score.
          </p>
        ) : null}
        {job.score_boosts[0] ? (
          <p className="mt-2 flex items-center gap-1 text-xs">
            <TrendingUp className="text-success size-3.5 shrink-0" />
            <span>
              Biggest boost: <span className="font-medium">{job.score_boosts[0].name}</span>{' '}
              <span className="text-success font-semibold tabular-nums">
                +{job.score_boosts[0].points}
              </span>
            </span>
          </p>
        ) : null}
      </div>

      {/* Pushes the actions to the bottom, so cards in a row line up. */}
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
        <Button
          size="sm"
          className="flex-1"
          render={<a href={job.url} target="_blank" rel="noopener noreferrer" />}
          nativeButton={false}
          onClick={recordApply}
          disabled={track.isPending}
        >
          {track.isPending ? 'Adding…' : 'Apply'}
          <ExternalLink />
        </Button>
        <Button size="sm" variant="outline" onClick={() => setExplaining(true)}>
          <Info />
          Why
        </Button>
        <Button size="sm" variant="ghost" onClick={checkInDetail} aria-label="Full check">
          <ScanSearch />
        </Button>
      </div>
      {track.isError ? (
        <div className="mt-2">
          <InlineError>
            The company page opened, but we couldn&apos;t add it to your applications.{' '}
            {errorMessage(track.error)}
          </InlineError>
        </div>
      ) : null}

      <ScoreSheet
        job={job}
        open={explaining}
        onOpenChange={setExplaining}
        onFullCheck={checkInDetail}
        onApply={recordApply}
      />
    </li>
  );
}

function ScoreSheet({
  job,
  open,
  onOpenChange,
  onFullCheck,
  onApply,
}: {
  job: CareerJob;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onFullCheck: () => void;
  onApply: () => void;
}) {
  const required = job.skill_results.filter((s) => s.required);
  const niceToHave = job.skill_results.filter((s) => !s.required);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 overflow-y-auto p-0 sm:max-w-md">
        <SheetHeader className="border-b p-6">
          <SheetTitle className="pr-6">{job.title}</SheetTitle>
          <SheetDescription>
            {job.company}
            {placesLabel(job) ? ` · ${placesLabel(job)}` : ''}
            {job.work_mode !== 'not_stated' ? ` · ${WORK_MODE_META[job.work_mode].label}` : ''}
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-5 p-6">
          <div className="flex items-center gap-4">
            <ScoreBadge score={job.score} />
            <p className="text-sm">{job.fit_note}</p>
          </div>
          <ScoreBoosts job={job} />
          {job.skill_results.length > 0 ? (
            <div>
              <SkillGroup label="Required skills" skills={required} />
              <SkillGroup label="Nice to have" skills={niceToHave} />
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              This posting names no skills we recognise, so it has no score.
            </p>
          )}
          <p className="text-muted-foreground text-xs">Location on the site: {job.location}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              render={<a href={job.url} target="_blank" rel="noopener noreferrer" />}
              nativeButton={false}
              onClick={onApply}
            >
              Apply on company site
              <ExternalLink />
            </Button>
            <Button variant="outline" onClick={onFullCheck}>
              <ScanSearch />
              Full check
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
