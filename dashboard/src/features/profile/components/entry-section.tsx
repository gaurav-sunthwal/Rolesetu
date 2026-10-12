'use client';

import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { Field, inputClass } from '@/components/app/field';
import { SectionCard } from '@/components/app/section-card';
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
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

export type EntryField = {
  name: string;
  label: string;
  type?: 'text' | 'month' | 'year' | 'url' | 'textarea';
  required?: boolean;
  placeholder?: string;
  hint?: string;
  /** Takes the full row instead of half. */
  wide?: boolean;
};

type Values = Record<string, string>;

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const YEAR = /^(19[5-9]\d|20\d\d|2100)$/;

function ruleFor(field: EntryField) {
  return {
    required: field.required ? `Enter ${field.label.toLowerCase()}` : false,
    maxLength:
      field.type === 'textarea'
        ? { value: 4000, message: 'Keep this under 4,000 characters' }
        : { value: 160, message: 'Keep this under 160 characters' },
    validate: (value: string) => {
      if (!value) return true;
      if (field.type === 'month' && !MONTH.test(value)) return 'Use the format YYYY-MM';
      if (field.type === 'year' && !YEAR.test(value)) return 'Enter a four-digit year';
      if (field.type === 'url' && !URL.canParse(value))
        return 'Enter the full link, starting with https://';
      return true;
    },
  };
}

/**
 * A profile list (experience, projects, education): shows the entries and edits
 * one at a time in a dialog. Each section supplies its fields and how an item
 * maps to and from the form.
 */
export function EntrySection<T extends { id: string }>({
  title,
  description,
  noun,
  items,
  maxItems,
  fields,
  toValues,
  fromValues,
  checkValues,
  summarize,
  onChange,
}: {
  title: string;
  description: string;
  noun: string;
  items: T[];
  maxItems: number;
  fields: EntryField[];
  toValues: (item: T | null) => Values;
  fromValues: (values: Values, id: string) => T;
  /** Cross-field check; returns a field name and message, or null. */
  checkValues?: (values: Values) => { field: string; message: string } | null;
  summarize: (item: T) => { title: string; subtitle: string; body?: string };
  onChange: (items: T[]) => void;
}) {
  const [editing, setEditing] = useState<{ item: T | null } | null>(null);
  const [removing, setRemoving] = useState<T | null>(null);
  const atLimit = items.length >= maxItems;

  return (
    <SectionCard
      title={title}
      description={description}
      action={
        <Button variant="outline" onClick={() => setEditing({ item: null })} disabled={atLimit}>
          <Plus />
          Add
        </Button>
      }
    >
      {items.length === 0 ? (
        <p className="text-muted-foreground text-sm">Nothing here yet.</p>
      ) : (
        <ul className="divide-border -my-3 divide-y">
          {items.map((item) => {
            const summary = summarize(item);
            return (
              <li key={item.id} className="flex items-start gap-3 py-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{summary.title}</p>
                  <p className="text-muted-foreground text-sm">{summary.subtitle}</p>
                  {summary.body ? (
                    <p className="text-muted-foreground mt-1.5 line-clamp-3 text-sm whitespace-pre-line">
                      {summary.body}
                    </p>
                  ) : null}
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Edit ${summary.title}`}
                  onClick={() => setEditing({ item })}
                >
                  <Pencil />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Remove ${summary.title}`}
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => setRemoving(item)}
                >
                  <Trash2 />
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="max-h-[92svh] overflow-y-auto rounded-3xl p-6 sm:max-w-lg">
          {editing ? (
            <EntryForm
              heading={editing.item ? `Edit ${noun}` : `Add ${noun}`}
              fields={fields}
              defaultValues={toValues(editing.item)}
              checkValues={checkValues}
              onCancel={() => setEditing(null)}
              onSave={(values) => {
                const next = fromValues(values, editing.item?.id ?? crypto.randomUUID());
                onChange(
                  editing.item
                    ? items.map((item) => (item.id === next.id ? next : item))
                    : [next, ...items],
                );
                setEditing(null);
              }}
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Remove this ${noun}?`}
        description={
          removing
            ? `"${summarize(removing).title}" will be removed from your profile, and future match scores will no longer use it as evidence.`
            : ''
        }
        confirmLabel="Remove"
        onConfirm={() => {
          if (removing) onChange(items.filter((item) => item.id !== removing.id));
          setRemoving(null);
        }}
      />
    </SectionCard>
  );
}

function EntryForm({
  heading,
  fields,
  defaultValues,
  checkValues,
  onSave,
  onCancel,
}: {
  heading: string;
  fields: EntryField[];
  defaultValues: Values;
  checkValues?: (values: Values) => { field: string; message: string } | null;
  onSave: (values: Values) => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<Values>({ defaultValues });

  function submit(values: Values) {
    const trimmed = Object.fromEntries(
      Object.entries(values).map(([key, value]) => [key, value.trim()]),
    );
    const problem = checkValues?.(trimmed);
    if (problem) return setError(problem.field, { message: problem.message });
    onSave(trimmed);
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle className="text-lg">{heading}</DialogTitle>
        <DialogDescription>
          Be specific about what you built and what you used. This is the evidence jobs are scored
          against.
        </DialogDescription>
      </DialogHeader>
      <form
        id="entry-form"
        noValidate
        onSubmit={handleSubmit(submit)}
        className="grid gap-4 sm:grid-cols-2"
      >
        {fields.map((field) => {
          const id = `entry-${field.name}`;
          const message = errors[field.name]?.message;
          const common = {
            id,
            placeholder: field.placeholder,
            'aria-invalid': !!message,
            ...register(field.name, ruleFor(field)),
          };
          return (
            <Field
              key={field.name}
              id={id}
              label={field.label}
              hint={field.hint}
              optional={!field.required}
              error={typeof message === 'string' ? message : undefined}
              className={cn(field.wide && 'sm:col-span-2')}
            >
              {field.type === 'textarea' ? (
                <Textarea rows={5} className="px-3.5 py-2.5" {...common} />
              ) : (
                <Input
                  type={field.type === 'month' ? 'month' : field.type === 'url' ? 'url' : 'text'}
                  inputMode={field.type === 'year' ? 'numeric' : undefined}
                  className={inputClass}
                  {...common}
                />
              )}
            </Field>
          );
        })}
      </form>
      <DialogFooter>
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" form="entry-form">
          Save
        </Button>
      </DialogFooter>
    </>
  );
}
