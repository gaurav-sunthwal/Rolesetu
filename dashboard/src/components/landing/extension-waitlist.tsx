'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { ArrowRight, CircleCheck, Mail } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { joinExtensionWaitlist } from '@/features/waitlist/api';
import { errorMessage } from '@/lib/api/client';

const schema = z.object({ email: z.email('Enter a valid email address') });
type Values = z.infer<typeof schema>;

/** Collects an email address to write to when the extension reaches the store. */
export function ExtensionWaitlist() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });
  const join = useMutation({ mutationFn: joinExtensionWaitlist });

  if (join.isSuccess) {
    return (
      <div role="status" className="bg-success/10 flex items-start gap-3 rounded-2xl p-4">
        <CircleCheck className="text-success mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-medium">You are on the list.</p>
          <p className="text-muted-foreground mt-0.5 text-sm">
            We will email {join.variables.email} the day the extension is in the Chrome Web Store.
          </p>
        </div>
      </div>
    );
  }

  const problem = errors.email?.message ?? (join.isError ? errorMessage(join.error) : null);

  return (
    <form noValidate onSubmit={handleSubmit((values) => join.mutate(values))}>
      <div className="bg-background focus-within:ring-ring/60 flex flex-col gap-2 rounded-2xl border p-2 transition-shadow focus-within:ring-2 sm:flex-row sm:items-center sm:pl-4">
        <Mail className="text-muted-foreground hidden size-5 shrink-0 sm:block" />
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          aria-label="Email address"
          aria-invalid={!!problem}
          aria-describedby={problem ? 'waitlist-error' : 'waitlist-hint'}
          placeholder="you@example.com"
          className="placeholder:text-muted-foreground h-12 w-full min-w-0 shrink-0 bg-transparent px-3 text-base outline-none sm:w-auto sm:flex-1 sm:shrink sm:px-0"
          {...register('email')}
        />
        <button
          type="submit"
          disabled={join.isPending}
          className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/60 flex h-12 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-base font-medium transition-[background-color,scale] outline-none focus-visible:ring-2 active:scale-[0.98] disabled:opacity-60 motion-reduce:transition-none"
        >
          {join.isPending ? 'Adding you…' : 'Notify me'}
          <ArrowRight className="size-4" />
        </button>
      </div>
      {problem ? (
        <p id="waitlist-error" role="alert" className="text-destructive mt-2.5 text-sm">
          {problem}
        </p>
      ) : (
        <p id="waitlist-hint" className="text-muted-foreground mt-2.5 text-sm">
          One email when it launches. Nothing else, and no account needed.
        </p>
      )}
    </form>
  );
}
