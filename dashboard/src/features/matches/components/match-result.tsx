'use client';

import { ExternalLink, Plus, RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { SectionCard } from '@/components/app/section-card';
import { Button } from '@/components/ui/button';
import { AddApplicationDialog } from '@/features/applications/components/add-application-dialog';
import { ExperienceNote } from '@/features/matches/components/experience-note';
import { ScoreRing } from '@/features/matches/components/score-ring';
import { bandOf, VERDICT_META } from '@/features/matches/score';
import { GapsCard } from '@/features/tailoring/components/gaps-card';
import type { Match, SkillResult } from '@/lib/api/types';
import { cn } from '@/lib/utils';

export function MatchResult({
  match,
  onCheckAnother,
}: {
  match: Match;
  onCheckAnother: () => void;
}) {
  const [tracking, setTracking] = useState(false);
  const score = match.score ?? 0;
  const band = bandOf(score);
  const required = match.skill_results.filter((skill) => skill.required);
  const niceToHave = match.skill_results.filter((skill) => !skill.required);
  const requiredMet = required.filter((skill) => skill.verdict !== 'missing').length;
  const title = [match.role, match.company].filter(Boolean).join(' · ') || 'This job';
  const details = [match.location, match.employment_type, match.salary].filter(
    (detail): detail is string => !!detail,
  );

  return (
    <div className="flex flex-col gap-5">
      <section className="bg-card flex flex-col items-center gap-6 rounded-4xl border p-6 text-center sm:flex-row sm:p-8 sm:text-left">
        <ScoreRing score={score} />
        <div className="min-w-0 flex-1">
          <p className={cn('text-sm font-semibold', band.text)}>{band.label}</p>
          <h2 className="mt-1 text-xl font-bold tracking-tight text-balance sm:text-2xl">
            {title}
          </h2>
          {details.length > 0 || match.url ? (
            <p className="text-muted-foreground mt-2 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-sm sm:justify-start">
              {details.map((detail) => (
                <span
                  key={detail}
                  className="bg-secondary rounded-full px-2.5 py-0.5 text-xs font-medium"
                >
                  {detail}
                </span>
              ))}
              {match.url ? (
                <a
                  href={match.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary inline-flex items-center gap-1 text-xs font-medium underline-offset-4 hover:underline"
                >
                  View listing
                  <ExternalLink className="size-3" />
                </a>
              ) : null}
            </p>
          ) : null}
          <p className="text-muted-foreground mt-2 text-sm">
            {required.length > 0
              ? `You show evidence for ${requiredMet} of ${required.length} required skills.`
              : 'This posting listed no hard requirements, only nice-to-haves.'}
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2 sm:justify-start">
            <Button onClick={() => setTracking(true)}>
              <Plus />
              Track this job
            </Button>
            <Button variant="outline" onClick={onCheckAnother}>
              <RotateCcw />
              Check another job
            </Button>
          </div>
        </div>
      </section>

      <ExperienceNote match={match} />

      <div className="grid items-start gap-5 lg:grid-cols-5">
        <SectionCard
          className="lg:col-span-3"
          title="How each skill was judged"
          description="Every verdict points at something in your own profile."
        >
          <SkillGroup label="Required" skills={required} />
          <SkillGroup label="Nice to have" skills={niceToHave} />
        </SectionCard>

        <GapsCard key={match.id} match={match} />
      </div>

      <AddApplicationDialog
        open={tracking}
        onOpenChange={setTracking}
        prefill={{ role: match.role, company: match.company, url: match.url, matchId: match.id }}
      />
    </div>
  );
}

function SkillGroup({ label, skills }: { label: string; skills: SkillResult[] }) {
  if (skills.length === 0) return null;
  return (
    <div className="not-first:mt-6">
      <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        {label}
      </h3>
      <ul className="divide-border mt-1 divide-y">
        {skills.map((skill) => {
          const verdict = VERDICT_META[skill.verdict];
          return (
            <li key={skill.name} className="flex items-start gap-3 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{skill.name}</p>
                <p className="text-muted-foreground mt-0.5 text-sm">
                  {skill.reason ?? 'Nothing in your profile supports this yet.'}
                </p>
                {skill.evidence_text ? (
                  <p className="text-muted-foreground/90 border-border mt-1.5 line-clamp-2 border-l-2 pl-2.5 text-xs">
                    {skill.evidence_text}
                  </p>
                ) : null}
              </div>
              <span className="bg-secondary flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
                <span className={cn('size-1.5 rounded-full', verdict.dot)} />
                {verdict.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
