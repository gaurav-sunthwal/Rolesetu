'use client';

import { Check, FileText, Loader2, Plus, TrendingUp } from 'lucide-react';
import { useState } from 'react';

import { InlineError } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { projectedScore } from '@/features/matches/score';
import type { TailoredResume, TailorRequest } from '@/features/tailoring/api';
import { TailorPreviewDialog } from '@/features/tailoring/components/tailor-preview-dialog';
import { useTailorResume } from '@/features/tailoring/hooks';
import { errorMessage } from '@/lib/api/client';
import type { CareerJob, ScoreBoost } from '@/lib/api/types';
import { cn } from '@/lib/utils';

// The resume update takes at most this many skills at once.
const MAX_SKILLS = 12;

function boostReason(boost: ScoreBoost): string {
  const kind = boost.required ? 'required' : 'nice to have';
  return boost.verdict === 'missing' ? `Missing, ${kind}` : `Only partly shown, ${kind}`;
}

/**
 * Which skills would raise this job's score most. The user ticks the ones they
 * really have, and one button puts them on their own resume, through the same
 * preview the job check uses: nothing is saved until they choose to.
 */
export function ScoreBoosts({ job }: { job: CareerJob }) {
  const [ticked, setTicked] = useState<string[]>([]);
  const [sent, setSent] = useState<TailorRequest | null>(null);
  const [result, setResult] = useState<TailoredResume | null>(null);
  const tailor = useTailorResume();

  if (job.score === null) return null;
  const short = job.skill_results.some((s) => s.verdict !== 'strong');
  if (job.score_boosts.length === 0) {
    if (!short || job.score_cap === null) return null;
    return (
      <p className="bg-secondary rounded-2xl p-4 text-sm">
        Your experience caps this job at {job.score_cap}, so adding skills won&apos;t raise it
        further. More years of experience would.
      </p>
    );
  }

  const { score: projected } = projectedScore(job, ticked);
  const current = job.score;

  function toggle(name: string) {
    setTicked((previous) =>
      previous.includes(name)
        ? previous.filter((item) => item !== name)
        : previous.length < MAX_SKILLS
          ? [...previous, name]
          : previous,
    );
  }

  function send(request: TailorRequest) {
    setSent(request);
    tailor.mutate(request, { onSuccess: setResult });
  }

  function move(skill: string, row: string) {
    if (!sent) return;
    send({
      ...sent,
      skills: (sent.skills ?? []).map((item) => (item.name === skill ? { ...item, row } : item)),
    });
  }

  return (
    <section aria-labelledby={`boosts-${job.id}`} className="bg-success/5 rounded-2xl border p-4">
      <h4 id={`boosts-${job.id}`} className="flex items-center gap-1.5 text-sm font-semibold">
        <TrendingUp className="text-success size-4" />
        How to raise this score
      </h4>
      <p className="text-muted-foreground mt-1 text-xs">
        Points each skill adds once it is on your resume. Tick only the ones you have really used.
      </p>

      <ol className="mt-3 flex flex-col gap-2.5">
        {job.score_boosts.map((boost) => {
          // "React or Angular" is met by any one of them, so each is its own choice.
          const options = boost.name.split(' or ');
          return (
            <li key={boost.name} className="flex items-start justify-between gap-3 text-sm">
              <div className="min-w-0">
                <span className="text-muted-foreground block text-xs">
                  {options.length > 1 ? 'Any one of these · ' : ''}
                  {boostReason(boost)}
                </span>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {options.map((option) => (
                    <SkillToggle
                      key={option}
                      on={ticked.includes(option)}
                      onClick={() => toggle(option)}
                    >
                      {option}
                    </SkillToggle>
                  ))}
                </div>
              </div>
              <span className="text-success shrink-0 pt-4 font-semibold tabular-nums">
                +{boost.points}
              </span>
            </li>
          );
        })}
      </ol>

      {job.score_cap !== null ? (
        <p className="text-muted-foreground mt-3 text-xs">
          Experience caps this job at {job.score_cap}, so the gains stop there.
        </p>
      ) : null}

      <div className="mt-4 flex flex-col gap-2">
        {ticked.length > 0 ? (
          <p className="text-sm" aria-live="polite">
            <span className="tabular-nums">
              {current} → {projected}
            </span>{' '}
            <span className="text-success font-semibold">+{projected - current}</span>{' '}
            <span className="text-muted-foreground">once these are on your resume</span>
          </p>
        ) : null}
        <Button
          disabled={ticked.length === 0 || tailor.isPending}
          onClick={() => send({ skills: ticked.map((name) => ({ name, row: null })) })}
        >
          {tailor.isPending ? (
            <Loader2 className="animate-spin motion-reduce:animate-none" />
          ) : (
            <FileText />
          )}
          {tailor.isPending
            ? 'Updating your resume…'
            : ticked.length === 0
              ? 'Tick the skills you have'
              : `Add ${ticked.length} to my resume`}
        </Button>
        {tailor.isError && !result ? <InlineError>{errorMessage(tailor.error)}</InlineError> : null}
        <p className="text-muted-foreground text-xs">
          You see your own resume with only these skills added, in the same style, before anything
          is saved.
        </p>
      </div>

      <TailorPreviewDialog
        tailored={result}
        request={sent}
        moving={tailor.isPending}
        onMove={move}
        onClose={() => setResult(null)}
      />
    </section>
  );
}

function SkillToggle({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'focus-visible:ring-ring/50 flex items-center gap-1 rounded-full border px-2.5 py-1 text-sm font-medium transition-colors outline-none focus-visible:ring-3',
        on
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-card hover:bg-secondary border-border',
      )}
    >
      {on ? <Check className="size-3.5" /> : <Plus className="size-3.5 opacity-60" />}
      {children}
    </button>
  );
}
