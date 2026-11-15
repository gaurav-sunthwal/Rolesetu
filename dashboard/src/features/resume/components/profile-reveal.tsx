'use client';

import { useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Sparkles } from 'lucide-react';
import { useEffect, useRef } from 'react';

import { profileKeys } from '@/features/profile/hooks';
import { useLatestResume } from '@/features/resume/hooks';
import type { Profile } from '@/lib/api/types';

const SKILLS_SHOWN = 14;

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/**
 * Keeps the profile up to date while the AI is still reading the resume in the
 * background: when it finishes, the profile (with the skills and field it added)
 * is loaded again. Returns where it is.
 */
export function useResumeUnderstanding(): 'pending' | 'done' | 'failed' | null {
  const resume = useLatestResume();
  const queryClient = useQueryClient();
  const status = resume.data?.ai_status ?? null;
  const previous = useRef(status);

  useEffect(() => {
    if (previous.current === 'pending' && status === 'done') {
      // The profile and everything worked out from it (the field snapshot) changed.
      void queryClient.invalidateQueries({ queryKey: profileKeys.profile });
    }
    previous.current = status;
  }, [status, queryClient]);

  return status;
}

/** What was read from the resume, arriving piece by piece, and what the AI is doing. */
export function ProfileReveal({ profile }: { profile: Profile }) {
  const understanding = useResumeUnderstanding();
  const skills = profile.skills.slice(0, SKILLS_SHOWN);
  const more = profile.skills.length - skills.length;
  const counts = [
    plural(profile.skills.length, 'skill', 'skills'),
    plural(profile.experience.length, 'role', 'roles'),
    plural(profile.projects.length, 'project', 'projects'),
    plural(profile.education.length, 'school', 'schools'),
  ];

  return (
    <section
      aria-label="What we found on your resume"
      className="bg-card relative overflow-hidden rounded-3xl border p-5 sm:p-6"
    >
      <p className="pop-in text-muted-foreground text-sm">We found on your resume</p>
      <p
        className="pop-in mt-1 text-2xl font-semibold tracking-tight"
        style={{ '--pop-delay': '80ms' } as React.CSSProperties}
      >
        {profile.full_name || 'Your profile'}
      </p>
      {profile.headline ? (
        <p
          className="pop-in text-muted-foreground mt-0.5"
          style={{ '--pop-delay': '160ms' } as React.CSSProperties}
        >
          {profile.headline}
        </p>
      ) : null}

      <ul className="mt-4 flex flex-wrap gap-2" aria-label="Counts">
        {counts.map((count, index) => (
          <li
            key={count}
            className="pop-in bg-primary/10 text-primary rounded-full px-3 py-1 text-sm font-medium"
            style={{ '--pop-delay': `${240 + index * 70}ms` } as React.CSSProperties}
          >
            {count}
          </li>
        ))}
      </ul>

      {skills.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Skills">
          {skills.map((skill, index) => (
            <li
              key={skill.id}
              className="pop-in rounded-full border px-2.5 py-0.5 text-xs"
              style={{ '--pop-delay': `${520 + index * 45}ms` } as React.CSSProperties}
            >
              {skill.name}
            </li>
          ))}
          {more > 0 ? (
            <li
              className="pop-in text-muted-foreground px-1 py-0.5 text-xs"
              style={{ '--pop-delay': `${520 + skills.length * 45}ms` } as React.CSSProperties}
            >
              +{more} more
            </li>
          ) : null}
        </ul>
      ) : null}

      {understanding === 'pending' ? (
        <p
          className="pop-in bg-primary/5 text-foreground mt-5 flex items-start gap-2 rounded-2xl px-3.5 py-2.5 text-sm"
          role="status"
          style={{ '--pop-delay': '900ms' } as React.CSSProperties}
        >
          <Sparkles className="text-primary mt-0.5 size-4 shrink-0 animate-pulse motion-reduce:animate-none" />
          <span>
            Rolesetu&rsquo;s AI is understanding your field and finding more skills. Keep going:
            your profile updates by itself in a few seconds.
          </span>
        </p>
      ) : understanding === 'done' ? (
        <p
          className="pop-in text-success mt-5 flex items-center gap-2 text-sm font-medium"
          role="status"
        >
          <CheckCircle2 className="size-4 shrink-0" />
          Your profile is fully understood. Your field and skills are up to date.
        </p>
      ) : null}
    </section>
  );
}
