import { Briefcase, CircleAlert, CircleCheck, CircleHelp, TriangleAlert } from 'lucide-react';

import type { Match } from '@/lib/api/types';
import { cn } from '@/lib/utils';

type Experience = NonNullable<Match['experience']>;

const LOOK: Record<Experience['status'], { title: string; box: string; icon: typeof Briefcase }> = {
  meets: { title: 'Experience: you meet it', box: 'bg-success/10', icon: CircleCheck },
  open_to_freshers: {
    title: 'Experience: open to freshers',
    box: 'bg-success/10',
    icon: CircleCheck,
  },
  short: { title: 'Experience: slightly short', box: 'bg-warning/15', icon: CircleAlert },
  well_short: {
    title: 'Experience: well short of what this job asks',
    box: 'bg-destructive/10',
    icon: TriangleAlert,
  },
  not_stated: { title: 'Experience: not stated', box: 'bg-secondary', icon: CircleHelp },
};

function years(value: number, orMore = false): string {
  const plus = orMore ? '+' : '';
  if (value > 0 && value < 1) return `${Math.round(value * 12)}${plus} mo`;
  return `${value}${plus} yr${value === 1 ? '' : 's'}`;
}

/**
 * Where the user stands on experience for this job. Shown on every job check,
 * whether the news is good, bad or unknown, so it is never missed.
 */
export function ExperienceNote({ match }: { match: Match }) {
  const experience = match.experience;
  if (!experience) {
    // A check scored before experience was recorded: show its warning, if it had one.
    return match.seniority_note ? (
      <p className="bg-warning/15 flex items-start gap-3 rounded-2xl px-4 py-3 text-sm">
        <CircleAlert className="mt-0.5 size-4 shrink-0" />
        {match.seniority_note}
      </p>
    ) : null;
  }

  const look = LOOK[experience.status];
  const Icon = look.icon;
  const asked =
    experience.required_min === null
      ? 'Not stated'
      : experience.required_max && experience.required_max > experience.required_min
        ? `${experience.required_min} to ${years(experience.required_max)}`
        : experience.required_min === 0
          ? 'None'
          : years(experience.required_min, true);

  return (
    <section
      className={cn('flex flex-col gap-3 rounded-3xl px-5 py-4 sm:flex-row sm:gap-5', look.box)}
      aria-label="Experience"
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Icon className="mt-0.5 size-5 shrink-0" />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{look.title}</h3>
          <p className="mt-1 text-sm">{experience.summary}</p>
          {experience.quote && experience.source !== 'title' ? (
            <p className="text-muted-foreground border-foreground/20 mt-2 line-clamp-2 border-l-2 pl-2.5 text-xs">
              From the posting: “{experience.quote}”
            </p>
          ) : null}
        </div>
      </div>
      <dl className="flex shrink-0 gap-6 pl-8 sm:pl-0">
        <div>
          <dt className="text-muted-foreground text-xs">Job asks</dt>
          <dd className="text-lg font-bold">{asked}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">You have</dt>
          <dd className="text-lg font-bold">{years(experience.candidate_years)}</dd>
        </div>
      </dl>
    </section>
  );
}
