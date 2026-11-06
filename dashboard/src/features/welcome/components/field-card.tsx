'use client';

import { SectionCard } from '@/components/app/section-card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUpdateProfile } from '@/features/profile/hooks';
import type { Profile } from '@/lib/api/types';

const FIELD_OPTIONS: { value: string; label: string }[] = [
  { value: 'software', label: 'Software engineering' },
  { value: 'data', label: 'Data and analytics' },
  { value: 'hr', label: 'HR and recruiting' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'sales', label: 'Sales' },
  { value: 'operations', label: 'Operations and supply chain' },
  { value: 'finance', label: 'Accounting and finance' },
  { value: 'design', label: 'Design' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'education', label: 'Teaching and education' },
  { value: 'legal', label: 'Legal' },
  { value: 'electrical', label: 'Electrical engineering' },
  { value: 'mechanical', label: 'Mechanical engineering' },
  { value: 'construction', label: 'Construction and civil engineering' },
  { value: 'support', label: 'Customer support' },
  { value: 'product', label: 'Product management' },
];

export function FieldCard({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const mismatch =
    profile.inferred_field_key &&
    profile.field_key &&
    profile.inferred_field_key !== profile.field_key;

  return (
    <SectionCard title="Your line of work">
      <p className="text-muted-foreground mb-4 text-sm">
        Job checks and skill templates use this field. Change it if we guessed wrong.
      </p>
      {mismatch ? (
        <p className="text-warning mb-3 text-sm">
          Your roles suggest{' '}
          <strong>
            {FIELD_OPTIONS.find((o) => o.value === profile.inferred_field_key)?.label ??
              profile.inferred_field_key}
          </strong>
          ; we picked{' '}
          <strong>
            {FIELD_OPTIONS.find((o) => o.value === profile.field_key)?.label ?? profile.field_key}
          </strong>{' '}
          from your overall profile.
        </p>
      ) : null}
      <div className="flex flex-col gap-2">
        <Label htmlFor="field-key">Primary field</Label>
        <Select
          items={FIELD_OPTIONS}
          value={profile.field_key}
          onValueChange={(key) => {
            if (!key) return;
            update.mutate((current) => ({
              ...current,
              field_key: key,
              inferred_field_key: null,
            }));
          }}
        >
          <SelectTrigger id="field-key" className="w-full">
            <SelectValue placeholder="Choose your field" />
          </SelectTrigger>
          <SelectContent>
            {FIELD_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </SectionCard>
  );
}
