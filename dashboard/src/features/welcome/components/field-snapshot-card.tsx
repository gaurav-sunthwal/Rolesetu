'use client';

import { useQuery } from '@tanstack/react-query';

import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Skeleton } from '@/components/ui/skeleton';
import { SkillGroup } from '@/features/matches/components/match-result';
import { getFieldSnapshot } from '@/features/profile/api';
import { profileKeys, useProfile } from '@/features/profile/hooks';

/** Typical skills for the user's field — not a job score. */
export function FieldSnapshotCard() {
  const profile = useProfile();
  const snapshot = useQuery({
    queryKey: [...profileKeys.profile, 'field-snapshot', profile.data?.field_key],
    queryFn: getFieldSnapshot,
    enabled: profile.data !== undefined,
  });

  if (snapshot.isPending) {
    return (
      <SectionCard title="How you look in your field">
        <Skeleton className="h-24 w-full rounded-2xl" />
      </SectionCard>
    );
  }

  if (snapshot.isError) {
    return (
      <SectionCard title="How you look in your field">
        <ErrorState error={snapshot.error} onRetry={() => void snapshot.refetch()} />
      </SectionCard>
    );
  }

  const data = snapshot.data;
  if (data.catalog_status !== 'ready' || data.skills.length === 0) {
    return null;
  }

  const strong = data.skills.filter((s) => s.verdict === 'strong');
  const partial = data.skills.filter((s) => s.verdict === 'partial');
  const missing = data.skills.filter((s) => s.verdict === 'missing');

  return (
    <SectionCard
      title="How you look in your field"
      description={
        data.field_label
          ? `Compared with typical ${data.field_label} skills from your resume — not a job match score.`
          : undefined
      }
    >
      <div className="flex flex-col gap-4">
        {data.scope_summary ? (
          <p className="text-muted-foreground text-sm">{data.scope_summary}</p>
        ) : null}
        <SkillGroup label="Shown on your profile" skills={strong} />
        <SkillGroup label="Listed or dated" skills={partial} />
        <SkillGroup label="Not shown yet" skills={missing} />
      </div>
    </SectionCard>
  );
}
