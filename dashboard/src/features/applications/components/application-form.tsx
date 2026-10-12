'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { format } from 'date-fns';
import type { ReactNode } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { Field, inputClass } from '@/components/app/field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { StatusDot } from '@/features/applications/components/status-badge';
import { STATUS_ITEMS, STATUSES } from '@/features/applications/status';
import type { Application, ApplicationStatus } from '@/lib/api/types';

const schema = z.object({
  role: z.string().trim().min(1, 'Enter the role').max(160, 'Keep this under 160 characters'),
  company: z.string().trim().min(1, 'Enter the company').max(160, 'Keep this under 160 characters'),
  url: z.union([z.literal(''), z.url('Enter the full link, starting with https://')]),
  location: z.string().trim().max(160, 'Keep this under 160 characters'),
  status: z.enum(STATUSES),
  appliedOn: z.string(),
  contactEmail: z.union([z.literal(''), z.email('Enter a valid email address')]),
  notes: z.string().max(5000, 'Keep notes under 5,000 characters'),
});

export type ApplicationFormValues = z.infer<typeof schema>;

/** Shape shared by create and update requests. */
export function toRequestBody(values: ApplicationFormValues) {
  return {
    role: values.role,
    company: values.company,
    url: values.url || null,
    location: values.location || null,
    status: values.status,
    // Midday local time, so the date does not shift across time zones.
    applied_at:
      values.status !== 'saved' && values.appliedOn
        ? new Date(`${values.appliedOn}T12:00:00`).toISOString()
        : null,
    contact_email: values.contactEmail || null,
    notes: values.notes.trim() || null,
  };
}

export function defaultsFrom(
  source?: Partial<Pick<Application, 'role' | 'company' | 'url' | 'location' | 'status'>> &
    Partial<Pick<Application, 'applied_at' | 'contact_email' | 'notes'>>,
): ApplicationFormValues {
  return {
    role: source?.role ?? '',
    company: source?.company ?? '',
    url: source?.url ?? '',
    location: source?.location ?? '',
    status: source?.status ?? 'saved',
    appliedOn: format(source?.applied_at ? new Date(source.applied_at) : new Date(), 'yyyy-MM-dd'),
    contactEmail: source?.contact_email ?? '',
    notes: source?.notes ?? '',
  };
}

export function ApplicationForm({
  formId,
  defaultValues,
  onSubmit,
  children,
}: {
  formId: string;
  defaultValues: ApplicationFormValues;
  onSubmit: (values: ApplicationFormValues) => void;
  children?: ReactNode;
}) {
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<ApplicationFormValues>({ resolver: zodResolver(schema), defaultValues });
  const status = useWatch({ control, name: 'status' });
  const id = (name: string) => `${formId}-${name}`;

  return (
    <form id={formId} onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={id('role')} label="Role" error={errors.role?.message}>
          <Input
            id={id('role')}
            className={inputClass}
            placeholder="Frontend Engineer"
            aria-invalid={!!errors.role}
            {...register('role')}
          />
        </Field>
        <Field id={id('company')} label="Company" error={errors.company?.message}>
          <Input
            id={id('company')}
            className={inputClass}
            placeholder="Acme Labs"
            aria-invalid={!!errors.company}
            {...register('company')}
          />
        </Field>
      </div>

      <Field id={id('url')} label="Job link" optional error={errors.url?.message}>
        <Input
          id={id('url')}
          type="url"
          inputMode="url"
          className={inputClass}
          placeholder="https://"
          aria-invalid={!!errors.url}
          {...register('url')}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={id('status')} label="Status">
          <Controller
            control={control}
            name="status"
            render={({ field }) => (
              <Select
                items={STATUS_ITEMS}
                value={field.value}
                onValueChange={(value) => value && field.onChange(value as ApplicationStatus)}
              >
                <SelectTrigger id={id('status')} className="w-full px-3.5 data-[size=default]:h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      <StatusDot status={item.value} className="self-center" />
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
        {status === 'saved' ? (
          <Field id={id('location')} label="Location" optional error={errors.location?.message}>
            <Input id={id('location')} className={inputClass} {...register('location')} />
          </Field>
        ) : (
          <Field id={id('appliedOn')} label="Applied on">
            <Input
              id={id('appliedOn')}
              type="date"
              className={inputClass}
              {...register('appliedOn')}
            />
          </Field>
        )}
      </div>

      {status === 'saved' ? null : (
        <Field id={id('location')} label="Location" optional error={errors.location?.message}>
          <Input id={id('location')} className={inputClass} {...register('location')} />
        </Field>
      )}

      <Field
        id={id('contactEmail')}
        label="Contact email"
        optional
        error={errors.contactEmail?.message}
      >
        <Input
          id={id('contactEmail')}
          type="email"
          className={inputClass}
          placeholder="recruiter@company.com"
          aria-invalid={!!errors.contactEmail}
          {...register('contactEmail')}
        />
      </Field>

      <Field id={id('notes')} label="Notes" optional error={errors.notes?.message}>
        <Textarea
          id={id('notes')}
          rows={3}
          className="px-3.5 py-2.5"
          placeholder="Referral, salary range, anything worth remembering"
          {...register('notes')}
        />
      </Field>

      {children}
    </form>
  );
}
