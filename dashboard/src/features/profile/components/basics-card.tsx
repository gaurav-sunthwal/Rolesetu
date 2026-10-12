'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Field, inputClass } from '@/components/app/field';
import { SectionCard } from '@/components/app/section-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useUpdateProfile } from '@/features/profile/hooks';
import { errorMessage } from '@/lib/api/client';
import type { Profile } from '@/lib/api/types';

const link = z.union([z.literal(''), z.url('Enter the full link, starting with https://')]);

const schema = z.object({
  fullName: z.string().trim().max(160, 'Keep this under 160 characters'),
  headline: z.string().trim().max(160, 'Keep this under 160 characters'),
  location: z.string().trim().max(160, 'Keep this under 160 characters'),
  phone: z.string().trim().max(40, 'Keep this under 40 characters'),
  linkedin: link,
  github: link,
  portfolio: link,
});

type FormValues = z.infer<typeof schema>;

function valuesOf(profile: Profile): FormValues {
  return {
    fullName: profile.full_name ?? '',
    headline: profile.headline ?? '',
    location: profile.location ?? '',
    phone: profile.phone ?? '',
    linkedin: profile.links.linkedin ?? '',
    github: profile.links.github ?? '',
    portfolio: profile.links.portfolio ?? '',
  };
}

export function BasicsCard({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: valuesOf(profile) });

  function onSubmit(values: FormValues) {
    update.mutate(
      (current) => ({
        ...current,
        full_name: values.fullName || null,
        headline: values.headline || null,
        location: values.location || null,
        phone: values.phone || null,
        links: {
          linkedin: values.linkedin || null,
          github: values.github || null,
          portfolio: values.portfolio || null,
        },
      }),
      {
        onSuccess: (saved) => {
          reset(valuesOf(saved));
          toast.success('Profile saved');
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  return (
    <SectionCard title="About you" description="Used to fill application forms for you.">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="full-name" label="Full name" error={errors.fullName?.message}>
            <Input
              id="full-name"
              autoComplete="name"
              className={inputClass}
              {...register('fullName')}
            />
          </Field>
          <Field id="headline" label="Headline" error={errors.headline?.message}>
            <Input
              id="headline"
              className={inputClass}
              placeholder="Frontend engineer"
              {...register('headline')}
            />
          </Field>
          <Field id="location" label="Location" error={errors.location?.message}>
            <Input
              id="location"
              className={inputClass}
              placeholder="Bengaluru, India"
              {...register('location')}
            />
          </Field>
          <Field id="phone" label="Phone" error={errors.phone?.message}>
            <Input
              id="phone"
              type="tel"
              autoComplete="tel"
              className={inputClass}
              {...register('phone')}
            />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="linkedin" label="LinkedIn" error={errors.linkedin?.message}>
            <Input
              id="linkedin"
              type="url"
              className={inputClass}
              placeholder="https://linkedin.com/in/"
              aria-invalid={!!errors.linkedin}
              {...register('linkedin')}
            />
          </Field>
          <Field id="github" label="GitHub" error={errors.github?.message}>
            <Input
              id="github"
              type="url"
              className={inputClass}
              placeholder="https://github.com/"
              aria-invalid={!!errors.github}
              {...register('github')}
            />
          </Field>
          <Field id="portfolio" label="Portfolio" error={errors.portfolio?.message}>
            <Input
              id="portfolio"
              type="url"
              className={inputClass}
              placeholder="https://"
              aria-invalid={!!errors.portfolio}
              {...register('portfolio')}
            />
          </Field>
        </div>
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={!isDirty || update.isPending}>
            {update.isPending ? 'Saving…' : 'Save changes'}
          </Button>
          {isDirty ? (
            <p className="text-muted-foreground text-xs">You have unsaved changes.</p>
          ) : null}
        </div>
      </form>
    </SectionCard>
  );
}
