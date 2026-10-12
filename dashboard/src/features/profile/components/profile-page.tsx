'use client';

import { Check } from 'lucide-react';
import { useCallback, useState } from 'react';
import { toast } from 'sonner';

import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Skeleton } from '@/components/ui/skeleton';
import { BasicsCard } from '@/features/profile/components/basics-card';
import { type EntryField, EntrySection } from '@/features/profile/components/entry-section';
import { SavedAnswersCard } from '@/features/profile/components/saved-answers-card';
import { SkillsCard } from '@/features/profile/components/skills-card';
import { useProfile, useUpdateProfile } from '@/features/profile/hooks';
import { ResumeCard } from '@/features/resume/components/resume-card';
import { errorMessage } from '@/lib/api/client';
import type {
  EducationItem,
  ExperienceItem,
  Profile,
  ProfileWrite,
  ProjectItem,
} from '@/lib/api/types';
import { formatMonth } from '@/lib/format';
import { cn } from '@/lib/utils';

const EXPERIENCE_FIELDS: EntryField[] = [
  { name: 'title', label: 'Job title', required: true, placeholder: 'Frontend Developer' },
  { name: 'company', label: 'Company', required: true },
  { name: 'start', label: 'Start', type: 'month' },
  { name: 'end', label: 'End', type: 'month', hint: 'Leave empty if you work here now.' },
  { name: 'location', label: 'Location', wide: true },
  {
    name: 'description',
    label: 'What you did',
    type: 'textarea',
    wide: true,
    placeholder:
      'Built the seller dashboard in React and TypeScript, wrote Vitest tests for checkout…',
  },
];

const PROJECT_FIELDS: EntryField[] = [
  { name: 'name', label: 'Project name', required: true, wide: true },
  {
    name: 'tech',
    label: 'Tech used',
    wide: true,
    placeholder: 'Next.js, PostgreSQL, Docker',
    hint: 'Separate with commas.',
  },
  { name: 'url', label: 'Link', type: 'url', wide: true, placeholder: 'https://' },
  { name: 'description', label: 'What it does and what you built', type: 'textarea', wide: true },
];

const EDUCATION_FIELDS: EntryField[] = [
  { name: 'school', label: 'School', required: true, wide: true },
  { name: 'degree', label: 'Degree', required: true, placeholder: 'B.Tech' },
  { name: 'field', label: 'Field of study', placeholder: 'Computer Science' },
  { name: 'startYear', label: 'Start year', type: 'year', placeholder: '2019' },
  { name: 'endYear', label: 'End year', type: 'year', placeholder: '2023' },
];

function checklistFor(profile: Profile) {
  return [
    { label: 'Name and headline', done: !!profile.full_name && !!profile.headline },
    { label: 'At least 5 skills', done: profile.skills.length >= 5 },
    { label: 'A role you have held', done: profile.experience.length > 0 },
    { label: 'A project', done: profile.projects.length > 0 },
    { label: 'Education', done: profile.education.length > 0 },
    {
      label: 'A profile link',
      done: !!(profile.links.linkedin || profile.links.github || profile.links.portfolio),
    },
  ];
}

export function ProfilePage() {
  const profile = useProfile();
  const update = useUpdateProfile();
  // Bumped after a resume import, so the basics form reloads the new values.
  const [importCount, setImportCount] = useState(0);
  const handleImported = useCallback(() => setImportCount((count) => count + 1), []);

  if (profile.isPending) {
    return (
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
        <Skeleton className="h-28 rounded-3xl" />
        <Skeleton className="h-72 rounded-3xl" />
        <Skeleton className="h-40 rounded-3xl" />
      </div>
    );
  }
  if (profile.isError) {
    return (
      <div className="mx-auto w-full max-w-5xl">
        <SectionCard>
          <ErrorState error={profile.error} onRetry={() => profile.refetch()} />
        </SectionCard>
      </div>
    );
  }

  const data = profile.data;
  const save = (change: (current: ProfileWrite) => ProfileWrite) =>
    update.mutate(change, { onError: (error) => toast.error(errorMessage(error)) });

  return (
    <div className="mx-auto grid w-full max-w-5xl items-start gap-5 lg:grid-cols-3">
      <div className="flex flex-col gap-5 lg:col-span-2">
        <ResumeCard profile={data} onApplied={handleImported} />
        <BasicsCard key={importCount} profile={data} />
        <SkillsCard profile={data} />

        <EntrySection<ExperienceItem>
          title="Experience"
          description="Roles you have held. The strongest evidence for a match."
          noun="role"
          items={data.experience}
          maxItems={30}
          fields={EXPERIENCE_FIELDS}
          toValues={(item) => ({
            title: item?.title ?? '',
            company: item?.company ?? '',
            start: item?.start ?? '',
            end: item?.end ?? '',
            location: item?.location ?? '',
            description: item?.description ?? '',
          })}
          fromValues={(values, id) => ({
            id,
            title: values.title,
            company: values.company,
            start: values.start || null,
            end: values.end || null,
            location: values.location || null,
            description: values.description,
          })}
          checkValues={(values) =>
            values.start && values.end && values.end < values.start
              ? { field: 'end', message: 'The end cannot be before the start' }
              : null
          }
          summarize={(item) => ({
            title: item.title,
            subtitle: item.start
              ? `${item.company} · ${formatMonth(item.start)} to ${item.end ? formatMonth(item.end) : 'present'}`
              : `${item.company} · Dates not set`,
            body: item.description,
          })}
          onChange={(experience) => save((current) => ({ ...current, experience }))}
        />

        <EntrySection<ProjectItem>
          title="Projects"
          description="Things you built, at work or on your own."
          noun="project"
          items={data.projects}
          maxItems={30}
          fields={PROJECT_FIELDS}
          toValues={(item) => ({
            name: item?.name ?? '',
            tech: item?.tech.join(', ') ?? '',
            url: item?.url ?? '',
            description: item?.description ?? '',
          })}
          fromValues={(values, id) => ({
            id,
            name: values.name,
            tech: values.tech
              .split(',')
              .map((entry) => entry.trim().slice(0, 60))
              .filter(Boolean)
              .slice(0, 25),
            url: values.url || null,
            description: values.description,
          })}
          summarize={(item) => ({
            title: item.name,
            subtitle: item.tech.length > 0 ? item.tech.join(' · ') : 'No tech listed',
            body: item.description,
          })}
          onChange={(projects) => save((current) => ({ ...current, projects }))}
        />

        <EntrySection<EducationItem>
          title="Education"
          description="Degrees and courses."
          noun="education entry"
          items={data.education}
          maxItems={10}
          fields={EDUCATION_FIELDS}
          toValues={(item) => ({
            school: item?.school ?? '',
            degree: item?.degree ?? '',
            field: item?.field ?? '',
            startYear: item?.start_year?.toString() ?? '',
            endYear: item?.end_year?.toString() ?? '',
          })}
          fromValues={(values, id) => ({
            id,
            school: values.school,
            degree: values.degree,
            field: values.field || null,
            start_year: values.startYear ? Number(values.startYear) : null,
            end_year: values.endYear ? Number(values.endYear) : null,
          })}
          checkValues={(values) =>
            values.startYear && values.endYear && Number(values.endYear) < Number(values.startYear)
              ? { field: 'endYear', message: 'The end year cannot be before the start year' }
              : null
          }
          summarize={(item) => ({
            title: item.field ? `${item.degree}, ${item.field}` : item.degree,
            subtitle: [item.school, [item.start_year, item.end_year].filter(Boolean).join(' to ')]
              .filter(Boolean)
              .join(' · '),
          })}
          onChange={(education) => save((current) => ({ ...current, education }))}
        />

        <SavedAnswersCard />
      </div>

      <aside className="flex flex-col gap-5 lg:sticky lg:top-20">
        <SectionCard>
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold">Profile strength</h2>
            <p className="text-2xl font-bold tabular-nums">{data.completeness}%</p>
          </div>
          <div
            className="bg-secondary mt-3 h-2 overflow-hidden rounded-full"
            role="progressbar"
            aria-label="Profile strength"
            aria-valuenow={data.completeness}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="bg-primary h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
              style={{ width: `${data.completeness}%` }}
            />
          </div>
          <ul className="mt-5 flex flex-col gap-2.5">
            {checklistFor(data).map((item) => (
              <li key={item.label} className="flex items-center gap-2.5 text-sm">
                <span
                  className={cn(
                    'flex size-5 shrink-0 items-center justify-center rounded-full border',
                    item.done && 'border-success bg-success text-success-foreground',
                  )}
                >
                  {item.done ? <Check className="size-3" /> : null}
                </span>
                <span className={cn(!item.done && 'text-muted-foreground')}>{item.label}</span>
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground mt-5 text-xs leading-relaxed">
            The more real detail here, the more accurate your match scores. Changing your profile
            refreshes scores the next time you check a job.
          </p>
        </SectionCard>
      </aside>
    </div>
  );
}
