'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { InlineError } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useAddCareerCompany } from '@/features/career-jobs/hooks';
import type { CompanyPicks } from '@/features/career-jobs/picks';
import { errorMessage } from '@/lib/api/client';
import type { CareerCompany } from '@/lib/api/types';

const addSchema = z.object({
  link: z.url('Paste the full link to the jobs page, starting with https://'),
});

export function CompanyPicker({
  open,
  onOpenChange,
  companies,
  picks,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: CareerCompany[];
  picks: CompanyPicks;
  onSave: (picks: CompanyPicks) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92svh] flex-col rounded-3xl p-6 sm:max-w-lg">
        {/* Mounted per open, so a cancelled edit starts again from the saved choice. */}
        {open ? (
          <PickerBody
            companies={companies}
            picks={picks}
            onSave={(next) => {
              onSave(next);
              onOpenChange(false);
            }}
            onCancel={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function PickerBody({
  companies,
  picks,
  onSave,
  onCancel,
}: {
  companies: CareerCompany[];
  picks: CompanyPicks;
  onSave: (picks: CompanyPicks) => void;
  onCancel: () => void;
}) {
  const allSlugs = companies.map((c) => c.slug);
  const [chosen, setChosen] = useState<Set<string>>(
    () => new Set(picks.all ? allSlugs : picks.slugs),
  );
  const [query, setQuery] = useState('');
  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? companies.filter((c) => c.name.toLowerCase().includes(needle)) : companies;
  }, [companies, query]);
  const everything = chosen.size === allSlugs.length;

  function toggle(slug: string) {
    setChosen((previous) => {
      const next = new Set(previous);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Companies to follow</DialogTitle>
        <DialogDescription>
          Jobs from these companies&apos; careers pages are checked every morning. Choose all of
          them, or only the ones you would join.
        </DialogDescription>
      </DialogHeader>

      <div className="mt-2 flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input
            type="search"
            aria-label="Search companies"
            placeholder="Search companies"
            className="h-10 rounded-full pl-9"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Button
          variant="outline"
          onClick={() => setChosen(everything ? new Set() : new Set(allSlugs))}
        >
          {everything ? 'Clear all' : 'Select all'}
        </Button>
      </div>

      <ul className="divide-border -mx-2 mt-2 min-h-0 flex-1 divide-y overflow-y-auto">
        {shown.map((company) => (
          <li key={company.slug}>
            <label className="hover:bg-muted/50 flex cursor-pointer items-center gap-3 rounded-xl px-2 py-2.5">
              <input
                type="checkbox"
                className="accent-primary size-4"
                checked={chosen.has(company.slug)}
                onChange={() => toggle(company.slug)}
              />
              <span className="flex-1 text-sm font-medium">
                {company.name}
                {company.added ? (
                  <span className="text-muted-foreground ml-1.5 text-xs font-normal">added</span>
                ) : null}
              </span>
              <span className="text-muted-foreground text-xs tabular-nums">
                {company.error ? 'could not read' : `${company.job_count} jobs`}
              </span>
            </label>
          </li>
        ))}
        {shown.length === 0 ? (
          <li className="text-muted-foreground px-2 py-6 text-center text-sm">
            No company by that name. Add it below with a link to its jobs page.
          </li>
        ) : null}
      </ul>

      <AddCompanyForm onAdded={(slug) => setChosen((previous) => new Set(previous).add(slug))} />

      <DialogFooter className="mt-2">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={chosen.size === 0}
          onClick={() => onSave(everything ? { all: true } : { all: false, slugs: [...chosen] })}
        >
          {everything ? 'Follow all companies' : `Follow ${chosen.size} companies`}
        </Button>
      </DialogFooter>
    </>
  );
}

function AddCompanyForm({ onAdded }: { onAdded: (slug: string) => void }) {
  const add = useAddCareerCompany();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(addSchema), defaultValues: { link: '' } });

  return (
    <form
      className="border-border mt-3 border-t pt-4"
      onSubmit={handleSubmit((values) =>
        add.mutate(values.link.trim(), {
          onSuccess: (company) => {
            onAdded(company.slug);
            reset();
          },
        }),
      )}
    >
      <label htmlFor="add-company" className="text-sm font-medium">
        Add a company
      </label>
      <p className="text-muted-foreground mt-0.5 text-xs">
        Paste the link to its jobs page. Sites on Workday, Greenhouse, Lever, Ashby and
        SmartRecruiters work.
      </p>
      <div className="mt-2 flex gap-2">
        <Input
          id="add-company"
          type="url"
          inputMode="url"
          placeholder="https://jobs.lever.co/company"
          className="h-10 rounded-full"
          aria-invalid={errors.link ? true : undefined}
          {...register('link')}
        />
        <Button type="submit" variant="outline" disabled={add.isPending}>
          <Plus />
          {add.isPending ? 'Reading…' : 'Add'}
        </Button>
      </div>
      <div className="mt-1.5" aria-live="polite">
        {errors.link ? <InlineError>{errors.link.message}</InlineError> : null}
        {add.isError ? <InlineError>{errorMessage(add.error)}</InlineError> : null}
        {add.isPending ? (
          <p className="text-muted-foreground text-xs">
            Reading the careers site. This can take up to a minute.
          </p>
        ) : null}
        {add.isSuccess ? (
          <p className="text-success text-xs">
            Added {add.data.name} with {add.data.job_count} recent jobs in India.
          </p>
        ) : null}
      </div>
    </form>
  );
}
