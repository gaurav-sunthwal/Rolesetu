'use client';

import { Building2, Inbox, SearchX, SlidersHorizontal, UserRound } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';

import { EmptyState, ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import type { CareerJobFilters } from '@/features/career-jobs/api';
import { CompanyPicker } from '@/features/career-jobs/components/company-picker';
import { JobCard } from '@/features/career-jobs/components/job-card';
import { useCareerCompanies, useCareerJobs } from '@/features/career-jobs/hooks';
import { type CompanyPicks, readPicks, savePicks } from '@/features/career-jobs/picks';
import { WORK_MODE_META, WORK_MODE_ORDER } from '@/features/career-jobs/work-mode';
import { useProfile } from '@/features/profile/hooks';
import type { WorkMode } from '@/lib/api/types';
import { timeAgo } from '@/lib/format';
import { cn } from '@/lib/utils';

// One card per row on phones, two on tablets, three on wide screens.
const GRID = 'grid gap-4 sm:grid-cols-2 xl:grid-cols-3';
const PANEL = 'bg-card rounded-3xl border';

function yearsLabel(years: number): string {
  if (years <= 0) return 'a fresher';
  return `someone with about ${years % 1 === 0 ? years : years.toFixed(1)} years`;
}

export function JobsPage() {
  const profile = useProfile();
  const companies = useCareerCompanies();
  const [picks, setPicks] = useState<CompanyPicks>(readPicks);
  const [places, setPlaces] = useState<string[]>([]);
  const [workModes, setWorkModes] = useState<WorkMode[]>([]);
  const [includeStretch, setIncludeStretch] = useState(true);
  const [picking, setPicking] = useState(false);

  const filters: CareerJobFilters = useMemo(
    () => ({ companies: picks.all ? [] : picks.slugs, places, workModes, includeStretch }),
    [picks, places, workModes, includeStretch],
  );
  const hasEvidence = profile.data
    ? profile.data.skills.length + profile.data.experience.length + profile.data.projects.length > 0
    : false;
  const list = useCareerJobs(filters, hasEvidence);
  const jobs = list.data?.pages.flatMap((page) => page.items) ?? [];
  const first = list.data?.pages[0];
  const companyCount = companies.data?.companies.length ?? 0;
  const collectedAt = first?.collected_at ?? companies.data?.collected_at ?? null;

  function updatePicks(next: CompanyPicks) {
    setPicks(next);
    savePicks(next);
    setPlaces([]);
    setWorkModes([]);
  }

  function togglePlace(place: string) {
    setPlaces((previous) =>
      previous.includes(place) ? previous.filter((p) => p !== place) : [...previous, place],
    );
  }

  function toggleWorkMode(mode: WorkMode) {
    setWorkModes((previous) =>
      previous.includes(mode) ? previous.filter((m) => m !== mode) : [...previous, mode],
    );
  }

  const filtered = places.length > 0 || workModes.length > 0 || !includeStretch;
  // Only worth a filter when some jobs say how they are worked.
  const modeCounts = first?.work_modes ?? [];
  const showModes = modeCounts.some((m) => m.mode !== 'not_stated') || workModes.length > 0;

  const percent = first?.scored_percent ?? 0;
  const scoring =
    profile.isPending || Boolean(first?.refreshing) || (hasEvidence && list.isPending && !first);

  const followingLabel = picks.all
    ? `All companies${companyCount ? ` · ${companyCount}` : ''}`
    : `${picks.slugs.length} ${picks.slugs.length === 1 ? 'company' : 'companies'}`;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight">Fresh jobs</h2>
            <span className="bg-primary/10 text-primary rounded-full px-2 py-0.5 text-xs font-semibold">
              Beta
            </span>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            Posted in the last 7 days on company careers pages, picked for your experience.
            {collectedAt ? ` Updated ${timeAgo(collectedAt)}.` : ''}
          </p>
        </div>
        <Button variant="outline" onClick={() => setPicking(true)} disabled={!companies.data}>
          <Building2 />
          {followingLabel}
        </Button>
      </div>

      {first ? (
        <p className="text-muted-foreground -mt-2 text-sm">
          Showing jobs for {yearsLabel(first.candidate_years)} of experience, from your profile,
          plus roles asking up to one year more.{' '}
          <Link href="/app/profile" className="text-primary underline-offset-4 hover:underline">
            Not right? Update your experience.
          </Link>
        </p>
      ) : null}

      {first && first.places.length > 0 ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div
            className="-mx-1 flex min-w-0 gap-1.5 overflow-x-auto px-1 py-1"
            role="group"
            aria-label="Filter by city"
          >
            <FilterPill active={places.length === 0} onClick={() => setPlaces([])}>
              All cities
            </FilterPill>
            {first.places.map((place) => (
              <FilterPill
                key={place.name}
                active={places.includes(place.name)}
                onClick={() => togglePlace(place.name)}
                count={place.count}
              >
                {place.name}
              </FilterPill>
            ))}
          </div>
          <div className="shrink-0 sm:ml-auto">
            <FilterPill active={includeStretch} onClick={() => setIncludeStretch((v) => !v)}>
              <SlidersHorizontal className="size-3.5" />
              Include stretch roles
            </FilterPill>
          </div>
        </div>
      ) : null}

      {first && showModes ? (
        <div
          className="-mx-1 -mt-2 flex min-w-0 gap-1.5 overflow-x-auto px-1 py-1"
          role="group"
          aria-label="Filter by work mode"
        >
          <FilterPill active={workModes.length === 0} onClick={() => setWorkModes([])}>
            Any work mode
          </FilterPill>
          {WORK_MODE_ORDER.map((mode) => {
            const count = modeCounts.find((m) => m.mode === mode)?.count ?? 0;
            if (count === 0 && !workModes.includes(mode)) return null;
            const meta = WORK_MODE_META[mode];
            const Icon = meta.icon;
            return (
              <FilterPill
                key={mode}
                active={workModes.includes(mode)}
                onClick={() => toggleWorkMode(mode)}
                count={count}
              >
                {Icon ? <Icon className="size-3.5" /> : null}
                {meta.label}
              </FilterPill>
            );
          })}
        </div>
      ) : null}

      {scoring ? <ScoreProgress percent={percent} showingPrevious={jobs.length > 0} /> : null}

      {profile.isError ? (
        <ErrorState className={PANEL} error={profile.error} onRetry={() => profile.refetch()} />
      ) : !profile.isPending && !hasEvidence ? (
        <EmptyState
          className={PANEL}
          icon={UserRound}
          title="Add your profile first"
          body="Jobs are matched to your skills and experience. Upload your resume or fill in your profile, then come back."
          action={
            <Button nativeButton={false} render={<Link href="/app/profile" />}>
              Go to your profile
            </Button>
          }
        />
      ) : list.isError && jobs.length === 0 ? (
        <ErrorState className={PANEL} error={list.error} onRetry={() => list.refetch()} />
      ) : scoring && jobs.length === 0 ? null : !collectedAt ? (
        <EmptyState
          className={PANEL}
          icon={Inbox}
          title="No jobs collected yet"
          body="Jobs are read from careers pages every morning. The first collection has not run yet; check back tomorrow."
        />
      ) : jobs.length === 0 ? (
        <EmptyState
          className={PANEL}
          icon={SearchX}
          title="No jobs fit right now"
          body={
            filtered
              ? 'Nothing matches these filters. Try more cities or work modes, or include stretch roles.'
              : 'None of the jobs from your companies this week match your experience. Follow more companies to see more.'
          }
          action={
            filtered ? (
              <Button
                variant="outline"
                onClick={() => {
                  setPlaces([]);
                  setWorkModes([]);
                  setIncludeStretch(true);
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Button variant="outline" onClick={() => setPicking(true)}>
                Choose companies
              </Button>
            )
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-muted-foreground text-sm">
            {first?.total} {first?.total === 1 ? 'job' : 'jobs'}, best match first
          </p>
          <ul className={cn(GRID, list.isPlaceholderData && 'opacity-60')}>
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </ul>
        </div>
      )}

      {list.hasNextPage ? (
        <Button
          variant="outline"
          className="mx-auto"
          onClick={() => list.fetchNextPage()}
          disabled={list.isFetchingNextPage}
        >
          {list.isFetchingNextPage ? 'Loading…' : 'Show more jobs'}
        </Button>
      ) : null}

      <CompanyPicker
        open={picking}
        onOpenChange={setPicking}
        companies={companies.data?.companies ?? []}
        picks={picks}
        onSave={updatePicks}
      />
    </div>
  );
}

function ScoreProgress({
  percent,
  showingPrevious,
}: {
  percent: number;
  showingPrevious: boolean;
}) {
  const shown = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <div className="bg-card rounded-3xl border px-4 py-3" aria-live="polite">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold">Matching jobs to your profile</p>
        <p className="text-sm font-semibold tabular-nums">{shown}%</p>
      </div>
      <div
        role="progressbar"
        aria-label="Matching jobs to your profile"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={shown}
        className="bg-secondary mt-2 h-2 overflow-hidden rounded-full"
      >
        <div
          className="bg-primary h-full rounded-full transition-[width] duration-300 ease-linear motion-reduce:transition-none"
          style={{ width: `${shown}%` }}
        />
      </div>
      {showingPrevious ? (
        <p className="text-muted-foreground mt-2 text-xs">
          Open any job below. This list is what is already matched for your profile, and it keeps
          filling in.
        </p>
      ) : null}
    </div>
  );
}

function FilterPill({
  active,
  onClick,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'focus-visible:ring-ring/50 flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium transition-colors outline-none focus-visible:ring-3',
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'bg-card text-muted-foreground hover:text-foreground',
      )}
    >
      {children}
      {count !== undefined ? <span className="tabular-nums opacity-70">{count}</span> : null}
    </button>
  );
}
