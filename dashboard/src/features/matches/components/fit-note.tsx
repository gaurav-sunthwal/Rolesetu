import { ArrowRightLeft, ShieldAlert, TriangleAlert } from 'lucide-react';

import type { Match } from '@/lib/api/types';
import { cn } from '@/lib/utils';

type Limit = Match['limits'][number];

const LIMIT_TITLE: Record<Exclude<Limit['kind'], 'experience'>, string> = {
  field: 'Not your role',
  must_have: 'Missing a requirement the job insists on',
  thin: 'Too little in this posting to be sure',
};

/**
 * What held the score down besides skills: a job in another field, a licence
 * or degree the posting requires, or a posting too thin to judge. Experience
 * has its own note above, so it is left out here. Also says when the job is in
 * a related field, which is worth knowing even when nothing was capped.
 */
export function FitNote({ match }: { match: Match }) {
  const limits = match.limits.filter(
    (limit): limit is Limit & { kind: keyof typeof LIMIT_TITLE } => limit.kind !== 'experience',
  );
  const related = match.field_fit?.status === 'related' ? match.field_fit.summary : null;
  if (limits.length === 0 && !related) return null;

  const serious = limits.some((limit) => limit.kind !== 'thin');
  return (
    <section
      className={cn(
        'flex flex-col gap-3 rounded-3xl px-5 py-4',
        serious ? 'bg-destructive/10' : 'bg-warning/15',
      )}
      aria-label="Why this score is limited"
    >
      {limits.map((limit) => {
        const Icon =
          limit.kind === 'field'
            ? ArrowRightLeft
            : limit.kind === 'thin'
              ? TriangleAlert
              : ShieldAlert;
        return (
          <div key={limit.kind} className="flex items-start gap-3">
            <Icon className="mt-0.5 size-5 shrink-0" />
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">
                {LIMIT_TITLE[limit.kind]} · score held at {limit.limit}
              </h3>
              <p className="mt-1 text-sm">{limit.reason}</p>
            </div>
          </div>
        );
      })}
      {limits.length === 0 && related ? (
        <div className="flex items-start gap-3">
          <ArrowRightLeft className="mt-0.5 size-5 shrink-0" />
          <p className="text-sm">{related}</p>
        </div>
      ) : null}
    </section>
  );
}
