'use client';

import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, Check, ExternalLink, PartyPopper } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';

import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { BasicsCard } from '@/features/profile/components/basics-card';
import { SkillsCard } from '@/features/profile/components/skills-card';
import { useProfile } from '@/features/profile/hooks';
import { ResumeCard } from '@/features/resume/components/resume-card';
import { getExtensionStatus } from '@/features/settings/api';
import { ExtensionCard } from '@/features/settings/components/extension-card';
import { findExtension } from '@/features/settings/extension-bridge';
import { isProfileEmpty, markWelcomeDone } from '@/features/welcome/state';
import type { Profile } from '@/lib/api/types';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';

const STEPS = ['Upload resume', 'Check your details', 'Connect extension'] as const;
type Step = 0 | 1 | 2;

/**
 * The first thing a new user sees: upload a resume, check what was read from
 * it, and connect the browser extension. Each step reuses the same card as the
 * Profile and Settings pages, so it behaves exactly as they do.
 */
export function WelcomePage() {
  const profile = useProfile();

  if (profile.isPending) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
        <Skeleton className="h-20 rounded-3xl" />
        <Skeleton className="h-56 rounded-3xl" />
      </div>
    );
  }
  if (profile.isError) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <SectionCard>
          <ErrorState error={profile.error} onRetry={() => profile.refetch()} />
        </SectionCard>
      </div>
    );
  }
  // Someone with a profile already (they came back, or filled it elsewhere)
  // starts at checking it rather than at the upload.
  return <Steps profile={profile.data} initial={isProfileEmpty(profile.data) ? 0 : 1} />;
}

function Steps({ profile, initial }: { profile: Profile; initial: Step }) {
  const { user } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<Step>(initial);
  // Bumped after a resume import, so the details form reloads the new values.
  const [importCount, setImportCount] = useState(0);
  const handleImported = useCallback(() => {
    setImportCount((count) => count + 1);
    setStep(1);
  }, []);

  function finish() {
    if (user) markWelcomeDone(user.uid);
    router.push('/app');
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-medium tracking-[-0.03em] sm:text-3xl">Welcome to Rolesetu</h1>
        <p className="text-muted-foreground mt-1">
          Three quick steps, and your match score shows up on every job page you open.
        </p>
      </header>

      <Progress step={step} onPick={setStep} />

      {step === 0 ? (
        <>
          <StepIntro
            title="Start with your resume"
            body="We read your PDF and build your profile from it: skills, roles, projects and education. It takes about 30 seconds, and you can change anything after."
          />
          <ResumeCard profile={profile} onApplied={handleImported} />
          <Footer
            back={null}
            skipLabel="I'll fill it in myself"
            onSkip={() => setStep(1)}
            next={isProfileEmpty(profile) ? null : () => setStep(1)}
          />
        </>
      ) : step === 1 ? (
        <>
          <StepIntro
            title="Check your details"
            body="We filled these in from your resume. The extension uses them to score jobs and fill in application forms, so check your name, phone and links, or skip and fix them later on your profile page."
          />
          <BasicsCard key={importCount} profile={profile} />
          <SkillsCard profile={profile} />
          <FoundSummary profile={profile} />
          <Footer
            back={() => setStep(0)}
            skipLabel="Skip, I'll check later"
            onSkip={finish}
            next={() => setStep(2)}
          />
        </>
      ) : (
        <>
          <StepIntro
            title="Turn on the extension"
            body="Connect it once, and it shows your match score on LinkedIn, Naukri and Indeed job pages and fills in application forms for you."
          />
          <ExtensionCard />
          <AllSet onFinish={finish} />
          <Footer back={() => setStep(1)} skipLabel="I'll do this later" onSkip={finish} />
        </>
      )}
    </div>
  );
}

function Progress({ step, onPick }: { step: Step; onPick: (step: Step) => void }) {
  return (
    <ol className="grid grid-cols-3 gap-2" aria-label="Setup steps">
      {STEPS.map((label, index) => {
        const done = index < step;
        const current = index === step;
        return (
          <li key={label}>
            <button
              type="button"
              // Going back is always fine; going ahead is done with the buttons below.
              disabled={index >= step}
              onClick={() => onPick(index as Step)}
              aria-current={current ? 'step' : undefined}
              className="group w-full text-left disabled:cursor-default"
            >
              <span
                className={cn(
                  'block h-1.5 rounded-full transition-colors motion-reduce:transition-none',
                  done || current ? 'bg-primary' : 'bg-secondary',
                )}
              />
              <span
                className={cn(
                  'mt-2 flex items-center gap-1.5 text-xs font-medium sm:text-sm',
                  current ? 'text-foreground' : 'text-muted-foreground',
                  done && 'group-hover:text-foreground',
                )}
              >
                {done ? <Check className="text-success size-3.5 shrink-0" /> : null}
                <span className="truncate">{label}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function StepIntro({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-muted-foreground mt-1 text-sm">{body}</p>
    </div>
  );
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** Roles, projects and education are longer forms: shown as counts, edited on the Profile page. */
function FoundSummary({ profile }: { profile: Profile }) {
  return (
    <SectionCard>
      <p className="text-sm font-medium">
        {plural(profile.experience.length, 'role', 'roles')} ·{' '}
        {plural(profile.projects.length, 'project', 'projects')} ·{' '}
        {plural(profile.education.length, 'education entry', 'education entries')}
      </p>
      <p className="text-muted-foreground mt-1 text-sm">
        You can add or fix these any time on your{' '}
        <Link href="/app/profile" className="text-foreground underline underline-offset-4">
          profile page
        </Link>
        .
      </p>
    </SectionCard>
  );
}

/** Shown once the extension in this browser holds this account's key. */
function AllSet({ onFinish }: { onFinish: () => void }) {
  // Same keys as the extension card, so this updates the moment it connects.
  const status = useQuery({ queryKey: ['extension', 'status'], queryFn: getExtensionStatus });
  const browser = useQuery({
    queryKey: ['extension', 'browser'],
    queryFn: findExtension,
    staleTime: 0,
  });
  if (status.data?.connected !== true || browser.data?.connected !== true) return null;

  return (
    <section
      role="status"
      className="border-success/30 bg-success/10 rounded-3xl border p-5 sm:p-6"
    >
      <div className="flex items-start gap-3">
        <PartyPopper className="text-success mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-semibold">You&apos;re all set</p>
          <p className="text-muted-foreground mt-1 text-sm">
            Open any job on LinkedIn, Naukri or Indeed. Your match score appears on the page, and
            the extension can fill in the application form for you.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              nativeButton={false}
              render={<a href="https://www.linkedin.com/jobs/" target="_blank" rel="noreferrer" />}
            >
              Open LinkedIn Jobs
              <ExternalLink data-icon="inline-end" />
            </Button>
            <Button variant="outline" onClick={onFinish}>
              Go to my dashboard
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer({
  back,
  next,
  skipLabel,
  onSkip,
}: {
  back: (() => void) | null;
  next?: (() => void) | null;
  skipLabel?: string;
  onSkip?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-5">
      <div>
        {back ? (
          <Button variant="ghost" onClick={back}>
            <ArrowLeft />
            Back
          </Button>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {skipLabel && onSkip ? (
          <Button variant="ghost" onClick={onSkip}>
            {skipLabel}
          </Button>
        ) : null}
        {next ? (
          <Button onClick={next}>
            Continue
            <ArrowRight data-icon="inline-end" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
