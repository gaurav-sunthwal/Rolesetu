import { Globe } from 'lucide-react';

import { cn } from '@/lib/utils';

type Verdict = 'strong' | 'partial' | 'missing';

type SkillResult = {
  name: string;
  required: boolean;
  verdict: Verdict;
  evidence?: string;
};

const SAMPLE: SkillResult[] = [
  {
    name: 'React',
    required: true,
    verdict: 'strong',
    evidence: 'Built a 40-screen admin app used by 3 teams',
  },
  {
    name: 'TypeScript',
    required: true,
    verdict: 'strong',
    evidence: 'Migrated the payments service from JavaScript',
  },
  { name: 'PostgreSQL', required: true, verdict: 'strong', evidence: 'Designed the orders schema' },
  { name: 'Node.js', required: true, verdict: 'partial', evidence: 'One internal CLI tool' },
  { name: 'Docker', required: true, verdict: 'missing' },
  { name: 'GraphQL', required: false, verdict: 'strong', evidence: 'Storefront API client' },
  { name: 'AWS', required: false, verdict: 'missing' },
];

// Same weights the real matcher uses: each skill gets a verdict, code does the math.
const POINTS: Record<Verdict, number> = { strong: 1, partial: 0.5, missing: 0 };

function tally(skills: SkillResult[]) {
  let earned = 0;
  let possible = 0;
  for (const skill of skills) {
    const weight = skill.required ? 2 : 1;
    earned += POINTS[skill.verdict] * weight;
    possible += weight;
  }
  return { earned, possible, score: Math.round((earned / possible) * 100) };
}

const VERDICT_STYLE: Record<Verdict, { dot: string; text: string }> = {
  strong: { dot: 'bg-success', text: 'text-success' },
  partial: { dot: 'bg-warning', text: 'text-warning' },
  missing: { dot: 'bg-destructive', text: 'text-destructive' },
};

const SEGMENTS = 24;

export const SAMPLE_JOB_URL = 'boards.example/acme-labs/frontend-engineer';

export function SampleMatch() {
  const { earned, possible, score } = tally(SAMPLE);
  const gaps = SAMPLE.filter((skill) => skill.verdict === 'missing').map((skill) => skill.name);
  const filled = Math.round((score / 100) * SEGMENTS);

  return (
    <div className="bg-card/95 text-card-foreground w-full overflow-hidden rounded-xl text-left shadow-2xl shadow-black/20 backdrop-blur">
      <div className="flex items-center gap-2.5 border-b px-4 py-3">
        <Globe className="text-muted-foreground size-3.5 shrink-0" />
        <p className="min-w-0 flex-1 truncate font-mono text-xs">{SAMPLE_JOB_URL}</p>
        <span className="text-muted-foreground shrink-0 font-mono text-[0.6875rem] tracking-wide uppercase">
          Sample
        </span>
      </div>

      <div className="flex items-end justify-between gap-4 px-4 pt-5">
        <div>
          <p className="text-muted-foreground text-xs">Frontend Engineer · Acme Labs</p>
          <p
            className="mt-1 text-5xl leading-none font-medium tracking-[-0.04em] tabular-nums"
            aria-label={`Match score ${score} out of 100`}
          >
            {score}
            <span className="text-muted-foreground ml-1 text-lg tracking-normal">/ 100</span>
          </p>
        </div>
        <p className="text-muted-foreground pb-1 text-right font-mono text-[0.6875rem] leading-4">
          {earned} of {possible}
          <br />
          weighted points
        </p>
      </div>
      <div aria-hidden className="mt-4 flex gap-[3px] px-4">
        {Array.from({ length: SEGMENTS }, (_, index) => (
          <span
            key={index}
            className={cn('h-2 flex-1 rounded-[2px]', index < filled ? 'bg-primary' : 'bg-muted')}
          />
        ))}
      </div>

      <ul className="mt-5 border-t">
        {SAMPLE.map((skill) => {
          const style = VERDICT_STYLE[skill.verdict];
          return (
            <li
              key={skill.name}
              className="flex items-center gap-3 border-b px-4 py-2.5 last:border-b-0"
            >
              <span className={cn('size-1.5 shrink-0 rounded-full', style.dot)} />
              <div className="min-w-0 flex-1 sm:flex sm:items-center sm:gap-3">
                <p className="shrink-0 text-sm font-medium sm:w-24">{skill.name}</p>
                <p className="text-muted-foreground truncate text-xs sm:min-w-0 sm:flex-1">
                  {skill.evidence ?? 'No evidence in your profile'}
                </p>
              </div>
              {skill.required ? null : (
                <span className="text-muted-foreground hidden shrink-0 font-mono text-[0.6875rem] sm:inline">
                  optional
                </span>
              )}
              <span className={cn('w-14 shrink-0 text-right font-mono text-xs', style.text)}>
                {skill.verdict}
              </span>
            </li>
          );
        })}
      </ul>

      <div className="bg-muted/60 flex items-center justify-between gap-3 border-t px-4 py-3 text-xs">
        <p>
          <span className="text-muted-foreground">Gaps to close:</span>{' '}
          <span className="font-medium">{gaps.join(', ')}</span>
        </p>
        <p className="text-muted-foreground shrink-0 font-mono text-[0.6875rem]">
          scored in seconds
        </p>
      </div>
    </div>
  );
}
