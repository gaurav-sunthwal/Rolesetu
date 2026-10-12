'use client';

import { Briefcase, Clock, Mail, Plus, Search, SearchX } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { toast } from 'sonner';

import { EmptyState, ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { AddApplicationDialog } from '@/features/applications/components/add-application-dialog';
import { ApplicationSheet } from '@/features/applications/components/application-sheet';
import { StatusDot } from '@/features/applications/components/status-badge';
import {
  useApplications,
  useApplicationStats,
  useUpdateApplication,
} from '@/features/applications/hooks';
import { STATUS_ITEMS, STATUS_META, STATUSES } from '@/features/applications/status';
import { InterviewsCard } from '@/features/inbox/components/interviews-card';
import { SyncButton, SyncNote } from '@/features/inbox/components/sync-button';
import { errorMessage } from '@/lib/api/client';
import type { Application, ApplicationStatus } from '@/lib/api/types';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

export function ApplicationsPage() {
  const [status, setStatus] = useState<ApplicationStatus | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const search = useDeferredValue(searchInput.trim());
  const [adding, setAdding] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const stats = useApplicationStats();
  const list = useApplications({ status, search });
  const applications = list.data?.pages.flatMap((page) => page.items) ?? [];
  const total = stats.data?.total ?? 0;
  const filtering = status !== null || search !== '';

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Your applications</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            {stats.data
              ? `${total} tracked · ${stats.data.sent} sent · ${stats.data.follow_ups_due} to follow up`
              : 'Every job you save or apply to, in one place.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <SyncButton />
          <Button onClick={() => setAdding(true)}>
            <Plus />
            Add application
          </Button>
        </div>
      </div>

      <SyncNote />

      {/* Only appears when an interview is coming up. */}
      <InterviewsCard hideWhenEmpty />

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div
          className="-mx-1 flex min-w-0 gap-1.5 overflow-x-auto px-1 py-1"
          role="group"
          aria-label="Filter by status"
        >
          <FilterPill
            active={status === null}
            onClick={() => setStatus(null)}
            count={stats.data?.total}
          >
            All
          </FilterPill>
          {STATUSES.map((value) => (
            <FilterPill
              key={value}
              active={status === value}
              onClick={() => setStatus(value)}
              count={stats.data?.by_status[value]}
            >
              <StatusDot status={value} />
              {STATUS_META[value].label}
            </FilterPill>
          ))}
        </div>
        <div className="relative shrink-0 lg:ml-auto lg:w-52">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2" />
          <Input
            type="search"
            aria-label="Search by role or company"
            placeholder="Search"
            className="bg-card h-10 rounded-full pr-4 pl-10"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>
      </div>

      <div className="bg-card overflow-hidden rounded-3xl border">
        {list.isPending ? (
          <ul className="divide-border divide-y">
            {Array.from({ length: 4 }, (_, index) => (
              <li key={index} className="flex items-center gap-4 p-4 sm:px-6">
                <Skeleton className="size-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
                <Skeleton className="h-9 w-28 rounded-full" />
              </li>
            ))}
          </ul>
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : applications.length === 0 ? (
          filtering ? (
            <EmptyState
              icon={SearchX}
              title="Nothing matches"
              body="No applications fit this filter. Try a different status or search."
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setStatus(null);
                    setSearchInput('');
                  }}
                >
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={Briefcase}
              title="No applications yet"
              body="Add a job you have applied to, or save one you are thinking about."
              action={
                <Button onClick={() => setAdding(true)}>
                  <Plus />
                  Add your first application
                </Button>
              }
            />
          )
        ) : (
          <ul className={cn('divide-border divide-y', list.isPlaceholderData && 'opacity-60')}>
            {applications.map((application) => (
              <ApplicationRow
                key={application.id}
                application={application}
                onOpen={() => setOpenId(application.id)}
              />
            ))}
          </ul>
        )}
      </div>

      {list.hasNextPage ? (
        <Button
          variant="outline"
          className="mx-auto"
          onClick={() => list.fetchNextPage()}
          disabled={list.isFetchingNextPage}
        >
          {list.isFetchingNextPage ? 'Loading…' : 'Load more'}
        </Button>
      ) : null}

      <AddApplicationDialog open={adding} onOpenChange={setAdding} />
      <ApplicationSheet applicationId={openId} onClose={() => setOpenId(null)} />
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

function ApplicationRow({ application, onOpen }: { application: Application; onOpen: () => void }) {
  const update = useUpdateApplication();

  function changeStatus(next: ApplicationStatus) {
    if (next === application.status) return;
    update.mutate(
      { id: application.id, body: { status: next } },
      {
        onSuccess: () => toast.success(`Moved to ${STATUS_META[next].label}`),
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  return (
    <li className="hover:bg-secondary/40 flex items-center gap-3 p-4 transition-colors sm:gap-4 sm:px-6">
      <button
        type="button"
        onClick={onOpen}
        className="focus-visible:ring-ring/50 flex min-w-0 flex-1 items-center gap-3 rounded-xl text-left outline-none focus-visible:ring-3 sm:gap-4"
      >
        <span className="bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold uppercase">
          {application.company.charAt(0)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{application.role}</span>
          <span className="text-muted-foreground block truncate text-sm">
            {application.company}
            {application.applied_at ? ` · Applied ${formatDate(application.applied_at)}` : ''}
          </span>
        </span>
        {application.needs_follow_up ? (
          <span className="bg-warning/20 hidden shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium sm:flex">
            <Clock className="size-3" />
            Follow up
          </span>
        ) : null}
        {application.match_score !== null ? (
          <span
            className="bg-secondary hidden shrink-0 rounded-full px-2.5 py-1 text-xs font-medium tabular-nums sm:block"
            title="Match score when you tracked this job"
          >
            {application.match_score} match
          </span>
        ) : null}
      </button>
      {application.gmail_url ? (
        // Beside the row button, not inside it: a link within a button is not valid.
        <a
          href={application.gmail_url}
          target="_blank"
          rel="noreferrer"
          title="Open the latest mail about this application in Gmail"
          className="text-muted-foreground hover:text-primary focus-visible:ring-ring/50 flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors outline-none focus-visible:ring-3"
        >
          <Mail className="size-3.5" />
          <span className="hidden sm:inline">Open in Gmail</span>
          <span className="sr-only sm:hidden">Open in Gmail</span>
        </a>
      ) : null}
      <Select
        items={STATUS_ITEMS}
        value={application.status}
        onValueChange={(value) => value && changeStatus(value as ApplicationStatus)}
        disabled={update.isPending}
      >
        <SelectTrigger
          aria-label={`Status of ${application.role} at ${application.company}`}
          className="bg-card shrink-0 rounded-full px-3 data-[size=default]:h-9"
        >
          <StatusDot status={application.status} />
          <SelectValue />
        </SelectTrigger>
        <SelectContent align="end">
          {STATUS_ITEMS.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              <StatusDot status={item.value} className="self-center" />
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </li>
  );
}
