'use client';

import { ArrowRight, Check, CircleCheck, FileText, Loader2, Plus } from 'lucide-react';
import Link from 'next/link';
import { type FormEvent, type ReactNode, useState } from 'react';

import { SectionCard } from '@/components/app/section-card';
import { InlineError } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import type { KeywordCheck, TailoredResume, TailorRequest } from '@/features/tailoring/api';
import { TailorPreviewDialog } from '@/features/tailoring/components/tailor-preview-dialog';
import { useKeywordCheck, useTailorResume } from '@/features/tailoring/hooks';
import { ApiError, errorMessage } from '@/lib/api/client';
import type { Match } from '@/lib/api/types';
import { cn } from '@/lib/utils';

const MAX_SKILLS = 12;

/**
 * The job's own words (its title and skills) checked against the user's
 * resume. Anything missing can be ticked, and one button makes a copy of the
 * resume with those changes in the same style.
 */
export function GapsCard({ match }: { match: Match }) {
  const check = useKeywordCheck(match.id);

  return (
    <SectionCard
      className="lg:col-span-2"
      title="Match your resume to this job"
      description="The words this job uses, checked against your resume. Tick what you want changed."
    >
      {check.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true">
          <Skeleton className="h-10 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
        </div>
      ) : check.isError ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm">{errorMessage(check.error)}</p>
          {check.error instanceof ApiError && check.error.status === 404 ? (
            <Button variant="outline" nativeButton={false} render={<Link href="/app/profile" />}>
              Upload my resume
            </Button>
          ) : (
            <Button variant="outline" onClick={() => void check.refetch()}>
              Try again
            </Button>
          )}
        </div>
      ) : (
        <Checklist keywords={check.data} />
      )}
    </SectionCard>
  );
}

function Checklist({ keywords }: { keywords: KeywordCheck }) {
  const title = keywords.title;
  const missing = keywords.skills.filter((skill) => skill.status === 'missing');
  const respellable = keywords.skills.filter((skill) => skill.status === 'different_spelling');
  const present = keywords.skills.filter((skill) => skill.status === 'present');

  const [extra, setExtra] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [respell, setRespell] = useState<string[]>([]);
  const [useHeadline, setUseHeadline] = useState(false);
  const [headline, setHeadline] = useState(title?.suggested ?? '');
  const [typed, setTyped] = useState('');
  // The last request sent, so a skill can be moved to another row and re-made.
  const [sent, setSent] = useState<TailorRequest | null>(null);
  const [result, setResult] = useState<TailoredResume | null>(null);
  const tailor = useTailorResume();

  const toggle = (list: string[], name: string, limit = MAX_SKILLS) =>
    list.includes(name)
      ? list.filter((item) => item !== name)
      : list.length < limit
        ? [...list, name]
        : list;

  function addTyped(event: FormEvent) {
    event.preventDefault();
    const name = typed.trim();
    if (!name) return;
    const known = [...missing.map((skill) => skill.name), ...extra];
    if (!known.some((option) => option.toLowerCase() === name.toLowerCase())) {
      setExtra((current) => [...current, name]);
    }
    if (!skills.includes(name)) setSkills((current) => toggle(current, name));
    setTyped('');
  }

  function send(request: TailorRequest) {
    setSent(request);
    tailor.mutate(request, { onSuccess: setResult });
  }

  function update() {
    send({
      skills: skills.map((name) => ({ name, row: null })),
      respell: respellable
        .filter((skill) => respell.includes(skill.name))
        .map((skill) => ({ written_as: skill.written_as ?? skill.name, wanted: skill.name })),
      headline: useHeadline && headline.trim() ? headline.trim() : null,
    });
  }

  function move(skill: string, row: string) {
    if (!sent) return;
    send({
      ...sent,
      skills: (sent.skills ?? []).map((item) => (item.name === skill ? { ...item, row } : item)),
    });
  }

  const headlineChosen = useHeadline && headline.trim().length >= 3;
  const count = skills.length + respell.length + (headlineChosen ? 1 : 0);
  const nothingToDo =
    missing.length === 0 && respellable.length === 0 && (!title || title.present || !title.current);

  return (
    <div className="flex flex-col gap-5">
      {title ? (
        <Group label="Job title">
          {title.present ? (
            <Done>Your resume already says “{title.wanted}”.</Done>
          ) : title.current === null ? (
            <p className="text-muted-foreground text-sm">
              The job is titled “{title.wanted}”. Your resume has no role line under your name to
              put it in.
            </p>
          ) : title.suggested === null ? (
            <p className="text-muted-foreground text-sm">
              The job is titled “{title.wanted}” and your resume says “{title.current}”. That is a
              different kind of role, so we do not suggest changing it.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              <label className="flex items-start gap-2.5 text-sm">
                <input
                  type="checkbox"
                  className="accent-primary mt-0.5 size-4"
                  checked={useHeadline}
                  onChange={(event) => setUseHeadline(event.target.checked)}
                />
                <span>
                  Change the line under my name from{' '}
                  <span className="font-medium">“{title.current}”</span> to:
                </span>
              </label>
              <Input
                aria-label="New headline"
                value={headline}
                maxLength={80}
                disabled={!useHeadline}
                onChange={(event) => setHeadline(event.target.value)}
              />
              <p className="text-muted-foreground text-xs">
                The job is titled “{title.wanted}”. The job titles you actually held are never
                changed.
              </p>
            </div>
          )}
        </Group>
      ) : null}

      {missing.length + extra.length > 0 ? (
        <Group label="Not in your resume" hint="Tick only the skills you really have.">
          <ul className="flex flex-wrap gap-2">
            {[...missing.map((skill) => skill.name), ...extra].map((name) => (
              <li key={name}>
                <Chip on={skills.includes(name)} onClick={() => setSkills(toggle(skills, name))}>
                  {name}
                </Chip>
              </li>
            ))}
          </ul>
        </Group>
      ) : null}

      {respellable.length > 0 ? (
        <Group
          label="Written differently"
          hint="Your resume has these, but not in the job's wording."
        >
          <ul className="flex flex-wrap gap-2">
            {respellable.map((skill) => (
              <li key={skill.name}>
                <Chip
                  on={respell.includes(skill.name)}
                  onClick={() => setRespell(toggle(respell, skill.name))}
                >
                  {skill.written_as}
                  <ArrowRight className="size-3 opacity-70" />
                  {skill.name}
                </Chip>
              </li>
            ))}
          </ul>
        </Group>
      ) : null}

      {present.length > 0 ? (
        <Group label="Already in your resume">
          <p className="text-muted-foreground text-sm">
            {present.map((skill) => skill.name).join(', ')}
          </p>
        </Group>
      ) : null}

      {nothingToDo && extra.length === 0 ? (
        <Done>Your resume already uses this job&apos;s wording. Nothing to change.</Done>
      ) : null}

      <form onSubmit={addTyped} className="flex gap-2">
        <label htmlFor="extra-skill" className="sr-only">
          Another skill you have
        </label>
        <Input
          id="extra-skill"
          value={typed}
          maxLength={60}
          placeholder="Another skill you have"
          onChange={(event) => setTyped(event.target.value)}
        />
        <Button type="submit" variant="outline" disabled={!typed.trim()}>
          Add
        </Button>
      </form>

      <div>
        <Button className="w-full" disabled={count === 0 || tailor.isPending} onClick={update}>
          {tailor.isPending ? (
            <Loader2 className="animate-spin motion-reduce:animate-none" />
          ) : (
            <FileText />
          )}
          {tailor.isPending
            ? 'Updating your resume…'
            : count === 0
              ? 'Tick what to change'
              : `Update my resume (${count} ${count === 1 ? 'change' : 'changes'})`}
        </Button>
        {tailor.isError && !result ? (
          <div className="mt-3">
            <InlineError>{errorMessage(tailor.error)}</InlineError>
          </div>
        ) : null}
        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
          You get a preview of your own resume with only these words changed, in the same style.
          Save it as your resume and the skills count in every job check from then on; or just
          download it for this one job.
        </p>
      </div>

      <TailorPreviewDialog
        tailored={result}
        request={sent}
        moving={tailor.isPending}
        onMove={move}
        onClose={() => setResult(null)}
      />
    </div>
  );
}

function Group({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        {label}
      </h3>
      {hint ? <p className="text-muted-foreground mt-0.5 text-xs">{hint}</p> : null}
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Done({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 text-sm font-medium">
      <CircleCheck className="text-success mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors',
        on
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-secondary hover:bg-secondary/70 border-transparent',
      )}
    >
      {on ? <Check className="size-3.5" /> : <Plus className="size-3.5 opacity-60" />}
      {children}
    </button>
  );
}
