'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight, CircleAlert, History, Link2, ScanSearch, UserRound } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { Field, inputClass } from '@/components/app/field';
import { SectionCard } from '@/components/app/section-card';
import { EmptyState, ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { MatchResult } from '@/features/matches/components/match-result';
import { useCreateMatch, useMatch, useRecentMatches } from '@/features/matches/hooks';
import { clearPendingJob, readPendingJob } from '@/features/preview/pending-job';
import { useProfile } from '@/features/profile/hooks';
import { errorMessage } from '@/lib/api/client';
import type { Match, MatchCreate } from '@/lib/api/types';
import { timeAgo } from '@/lib/format';

const MIN_LENGTH = 200;
const MAX_LENGTH = 20000;

const link = z.url('Enter the full link, starting with https://');

const linkSchema = z.object({ url: link });

const pasteSchema = z.object({
  jdText: z
    .string()
    .trim()
    .min(MIN_LENGTH, `Paste the full description (at least ${MIN_LENGTH} characters)`)
    .max(MAX_LENGTH, `That is too long. Keep it under ${MAX_LENGTH.toLocaleString()} characters`),
  url: z.union([z.literal(''), link]),
  role: z.string().trim().max(160),
  company: z.string().trim().max(160),
});

type LinkValues = z.infer<typeof linkSchema>;
type PasteValues = z.infer<typeof pasteSchema>;

export function CheckPage() {
  const profile = useProfile();
  const [activeId, setActiveId] = useState<string | null>(null);
  // A job looked up on the landing page before signing in is waiting to be scored.
  const [pendingUrl] = useState(readPendingJob);
  const [lastRequest, setLastRequest] = useState<MatchCreate | null>(
    pendingUrl ? { url: pendingUrl } : null,
  );
  const create = useCreateMatch();
  const match = useMatch(activeId);
  const startedPending = useRef(false);

  const hasEvidence = profile.data
    ? profile.data.skills.length +
        profile.data.experience.length +
        profile.data.projects.length +
        profile.data.education.length >
      0
    : false;

  const { mutate } = create;
  useEffect(() => {
    if (!pendingUrl || !hasEvidence || startedPending.current) return;
    startedPending.current = true;
    clearPendingJob();
    mutate({ url: pendingUrl }, { onSuccess: (created) => setActiveId(created.id) });
  }, [pendingUrl, hasEvidence, mutate]);

  function submit(request: MatchCreate) {
    setLastRequest(request);
    create.mutate(request, { onSuccess: (created) => setActiveId(created.id) });
  }

  function reset() {
    setActiveId(null);
    create.reset();
  }

  if (profile.isPending) {
    return (
      <Shell>
        <Skeleton className="h-80 w-full rounded-4xl" />
      </Shell>
    );
  }
  if (profile.isError) {
    return (
      <Shell>
        <SectionCard>
          <ErrorState error={profile.error} onRetry={() => profile.refetch()} />
        </SectionCard>
      </Shell>
    );
  }

  if (!hasEvidence) {
    return (
      <Shell>
        <SectionCard>
          <EmptyState
            icon={UserRound}
            title={pendingUrl ? 'One step left: add your experience' : 'Add your experience first'}
            body={
              pendingUrl
                ? 'Your job link is saved. A match score compares the job against your profile, so upload your resume or add a few skills, then come back here and it is scored straight away.'
                : 'A match score compares the job against your profile. Add a few skills, a role or a project, then come back.'
            }
            action={
              <Button nativeButton={false} render={<Link href="/app/profile" />}>
                Build your profile
                <ArrowRight />
              </Button>
            }
          />
        </SectionCard>
      </Shell>
    );
  }

  if (activeId !== null) {
    return (
      <Shell>
        {match.isError ? (
          <SectionCard>
            <ErrorState error={match.error} onRetry={() => match.refetch()} />
          </SectionCard>
        ) : !match.data || match.data.status === 'pending' ? (
          <Scoring startedAt={match.data?.created_at ?? null} />
        ) : match.data.status === 'failed' ? (
          <SectionCard>
            <div role="alert" className="flex flex-col items-center px-4 py-8 text-center">
              <span className="bg-destructive/10 text-destructive flex size-12 items-center justify-center rounded-full">
                <CircleAlert className="size-5" />
              </span>
              <p className="mt-4 font-semibold">This job could not be scored</p>
              <p className="text-muted-foreground mt-1 max-w-md text-sm">
                {match.data.error ?? 'Scoring failed. Please try again.'}
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {lastRequest ? (
                  <Button onClick={() => submit(lastRequest)} disabled={create.isPending}>
                    Try again
                  </Button>
                ) : null}
                <Button variant="outline" onClick={reset}>
                  Edit the job details
                </Button>
              </div>
            </div>
          </SectionCard>
        ) : (
          <MatchResult match={match.data} onCheckAnother={reset} />
        )}
      </Shell>
    );
  }

  return (
    <Shell>
      <JobForm
        defaults={lastRequest}
        pending={create.isPending}
        error={create.isError ? errorMessage(create.error) : null}
        onSubmit={submit}
      />
      <RecentChecks onOpen={setActiveId} />
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">{children}</div>;
}

function JobForm({
  defaults,
  pending,
  error,
  onSubmit,
}: {
  defaults: MatchCreate | null;
  pending: boolean;
  error: string | null;
  onSubmit: (request: MatchCreate) => void;
}) {
  // A link is the quick way in. Pasting is the fallback for pages we cannot read.
  const [mode, setMode] = useState<'link' | 'paste'>(defaults?.jd_text ? 'paste' : 'link');

  return (
    <section className="bg-card rounded-4xl border p-6 sm:p-8">
      <h2 className="text-2xl font-bold tracking-tight">How well do you fit this job?</h2>
      <p className="text-muted-foreground mt-1 text-sm">
        {mode === 'link'
          ? 'Paste the link to the job. We read the listing and score it against your profile.'
          : 'Paste the job description. You get a score, the evidence behind it, and the gaps.'}
      </p>

      {mode === 'link' ? (
        <LinkForm defaultUrl={defaults?.url ?? ''} pending={pending} onSubmit={onSubmit} />
      ) : (
        <PasteForm defaults={defaults} pending={pending} onSubmit={onSubmit} />
      )}

      {error ? (
        <div
          role="alert"
          className="bg-destructive/10 text-destructive mt-4 flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3 text-sm"
        >
          <span className="min-w-0 flex-1">{error}</span>
          {mode === 'link' ? (
            <Button variant="outline" size="sm" onClick={() => setMode('paste')}>
              Paste the description
            </Button>
          ) : null}
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setMode(mode === 'link' ? 'paste' : 'link')}
        className="text-muted-foreground hover:text-foreground mt-5 text-sm underline underline-offset-4"
      >
        {mode === 'link' ? 'No link? Paste the description instead' : 'Use a job link instead'}
      </button>
    </section>
  );
}

function LinkForm({
  defaultUrl,
  pending,
  onSubmit,
}: {
  defaultUrl: string;
  pending: boolean;
  onSubmit: (request: MatchCreate) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LinkValues>({
    resolver: zodResolver(linkSchema),
    defaultValues: { url: defaultUrl },
  });

  return (
    <form
      noValidate
      className="mt-6"
      onSubmit={handleSubmit((values) => onSubmit({ url: values.url.trim() }))}
    >
      <div className="bg-background focus-within:ring-ring/50 focus-within:border-ring flex flex-col gap-2 rounded-3xl border p-2 transition-shadow focus-within:ring-3 sm:flex-row sm:items-center sm:rounded-full sm:pl-5">
        <Link2 className="text-muted-foreground ml-3 hidden size-5 shrink-0 sm:ml-0 sm:block" />
        <input
          type="url"
          inputMode="url"
          autoComplete="off"
          aria-label="Job link"
          aria-invalid={!!errors.url}
          placeholder="https://internshala.com/job/detail/…"
          className="placeholder:text-muted-foreground h-11 min-w-0 flex-1 bg-transparent px-3 text-base outline-none sm:px-0"
          {...register('url')}
        />
        <Button type="submit" size="lg" disabled={pending} className="shrink-0">
          <ScanSearch />
          {pending ? 'Reading the page…' : 'Check my fit'}
        </Button>
      </div>
      {errors.url ? (
        <p role="alert" className="text-destructive mt-2 px-2 text-xs">
          {errors.url.message}
        </p>
      ) : (
        <p className="text-muted-foreground mt-2 px-2 text-xs">
          Works with listings that are open to the public. Pages that need you to sign in cannot be
          read.
        </p>
      )}
    </form>
  );
}

function PasteForm({
  defaults,
  pending,
  onSubmit,
}: {
  defaults: MatchCreate | null;
  pending: boolean;
  onSubmit: (request: MatchCreate) => void;
}) {
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<PasteValues>({
    resolver: zodResolver(pasteSchema),
    defaultValues: {
      jdText: defaults?.jd_text ?? '',
      url: defaults?.url ?? '',
      role: defaults?.role ?? '',
      company: defaults?.company ?? '',
    },
  });
  const length = useWatch({ control, name: 'jdText' }).trim().length;

  return (
    <form
      noValidate
      className="mt-6 flex flex-col gap-4"
      onSubmit={handleSubmit((values) =>
        onSubmit({
          jd_text: values.jdText,
          url: values.url || null,
          role: values.role || null,
          company: values.company || null,
        }),
      )}
    >
      <Field
        id="jd-text"
        label="Job description"
        error={errors.jdText?.message}
        hint={
          length === 0
            ? 'Copy everything from the posting, including the requirements.'
            : `${length.toLocaleString()} characters`
        }
      >
        <Textarea
          id="jd-text"
          rows={10}
          className="max-h-96 min-h-48 px-4 py-3"
          placeholder="Paste the full job description here"
          aria-invalid={!!errors.jdText}
          {...register('jdText')}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field id="jd-role" label="Role" optional>
          <Input
            id="jd-role"
            className={inputClass}
            placeholder="Detected if left blank"
            {...register('role')}
          />
        </Field>
        <Field id="jd-company" label="Company" optional>
          <Input
            id="jd-company"
            className={inputClass}
            placeholder="Detected if left blank"
            {...register('company')}
          />
        </Field>
        <Field id="jd-url" label="Job link" optional error={errors.url?.message}>
          <Input
            id="jd-url"
            type="url"
            inputMode="url"
            className={inputClass}
            placeholder="https://"
            aria-invalid={!!errors.url}
            {...register('url')}
          />
        </Field>
      </div>

      <div>
        <Button type="submit" size="lg" disabled={pending}>
          <ScanSearch />
          {pending ? 'Starting…' : 'Check my fit'}
        </Button>
      </div>
    </form>
  );
}

const STAGES = [
  { after: 0, text: 'Reading the job description' },
  { after: 8, text: 'Comparing each skill against your profile' },
  { after: 22, text: 'Nearly there. Longer descriptions take a little more time' },
] as const;

function Scoring({ startedAt }: { startedAt: string | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const elapsed = startedAt ? Math.max(0, (now - new Date(startedAt).getTime()) / 1000) : 0;
  const stage = STAGES.findLast((candidate) => elapsed >= candidate.after) ?? STAGES[0];

  return (
    <section
      aria-live="polite"
      className="bg-card flex flex-col items-center rounded-4xl border px-6 py-16 text-center"
    >
      <div className="border-secondary border-t-primary size-12 animate-spin rounded-full border-4 motion-reduce:animate-none" />
      <p className="mt-6 text-lg font-semibold">Scoring this job</p>
      <p className="text-muted-foreground mt-1 text-sm">{stage.text}…</p>
      <p className="text-muted-foreground mt-4 text-xs">
        This usually takes a moment. You can leave this page; the result is saved.
      </p>
    </section>
  );
}

function RecentChecks({ onOpen }: { onOpen: (id: string) => void }) {
  const recent = useRecentMatches(6);
  if (recent.isPending || recent.isError || recent.data.items.length === 0) return null;

  return (
    <SectionCard title="Recent checks">
      <ul className="divide-border -my-2 divide-y">
        {recent.data.items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onOpen(item.id)}
              className="hover:bg-secondary/50 focus-visible:ring-ring/50 -mx-2 flex w-[calc(100%+1rem)] items-center gap-3 rounded-2xl px-2 py-3 text-left transition-colors outline-none focus-visible:ring-3"
            >
              <span className="bg-secondary text-muted-foreground flex size-9 shrink-0 items-center justify-center rounded-full">
                <History className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {[item.role, item.company].filter(Boolean).join(' · ') || 'Untitled job'}
                </span>
                <span className="text-muted-foreground block text-xs">
                  {timeAgo(item.created_at)}
                </span>
              </span>
              <RecentStatus match={item} />
            </button>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

function RecentStatus({ match }: { match: Match }) {
  const label =
    match.status === 'completed' && match.score !== null
      ? `${match.score} match`
      : match.status === 'pending'
        ? 'Scoring…'
        : 'Failed';
  return (
    <span className="bg-secondary shrink-0 rounded-full px-2.5 py-1 text-xs font-medium tabular-nums">
      {label}
    </span>
  );
}
