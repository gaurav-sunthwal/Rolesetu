'use client';

import { Plus, X } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { inputClass } from '@/components/app/field';
import { SectionCard } from '@/components/app/section-card';
import { InlineError } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUpdateProfile } from '@/features/profile/hooks';
import { errorMessage } from '@/lib/api/client';
import type { Profile, SkillItem } from '@/lib/api/types';
import { newId } from '@/lib/format';

type Level = NonNullable<SkillItem['level']>;

const LEVELS: { value: Level; label: string }[] = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
];
const MAX_SKILLS = 100;

export function SkillsCard({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const [name, setName] = useState('');
  const [level, setLevel] = useState<Level>('intermediate');
  const [error, setError] = useState<string | null>(null);

  function save(skills: SkillItem[]) {
    update.mutate((current) => ({ ...current, skills }), {
      onError: (failure) => toast.error(errorMessage(failure)),
    });
  }

  function add() {
    const trimmed = name.trim();
    if (!trimmed) return setError('Type a skill to add');
    if (trimmed.length > 60) return setError('Keep a skill under 60 characters');
    if (profile.skills.some((skill) => skill.name.toLowerCase() === trimmed.toLowerCase())) {
      return setError(`${trimmed} is already on your list`);
    }
    if (profile.skills.length >= MAX_SKILLS)
      return setError(`You can list up to ${MAX_SKILLS} skills`);
    setError(null);
    setName('');
    save([...profile.skills, { id: newId(), name: trimmed, level }]);
  }

  return (
    <SectionCard
      title="Skills"
      description="The skills you would put on a resume. Job checks count each one, and say where in your roles and projects it shows up."
    >
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          add();
        }}
      >
        <Input
          aria-label="Skill name"
          aria-invalid={!!error}
          className={`${inputClass} sm:flex-1`}
          placeholder="e.g. TypeScript"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            setError(null);
          }}
        />
        <Select
          items={LEVELS}
          value={level}
          onValueChange={(value) => value && setLevel(value as Level)}
        >
          <SelectTrigger
            aria-label="Skill level"
            className="w-full px-3.5 data-[size=default]:h-10 sm:w-40"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LEVELS.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="submit" variant="outline" className="h-10">
          <Plus />
          Add
        </Button>
      </form>
      {error ? (
        <div className="mt-2">
          <InlineError>{error}</InlineError>
        </div>
      ) : null}

      {profile.skills.length === 0 ? (
        <p className="text-muted-foreground mt-4 text-sm">
          No skills yet. Add the ones you would put on a resume.
        </p>
      ) : (
        <ul className="mt-4 flex flex-wrap gap-2">
          {profile.skills.map((skill) => (
            <li
              key={skill.id}
              className="bg-secondary flex items-center gap-1.5 rounded-full py-1 pr-1 pl-3 text-sm font-medium"
            >
              {skill.name}
              {skill.level ? (
                <span className="text-muted-foreground text-xs font-normal capitalize">
                  {skill.level}
                </span>
              ) : null}
              <button
                type="button"
                aria-label={`Remove ${skill.name}`}
                onClick={() => save(profile.skills.filter((item) => item.id !== skill.id))}
                className="text-muted-foreground hover:bg-background hover:text-foreground focus-visible:ring-ring/50 flex size-6 items-center justify-center rounded-full outline-none focus-visible:ring-3"
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
