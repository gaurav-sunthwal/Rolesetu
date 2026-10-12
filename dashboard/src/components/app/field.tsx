import type { ReactNode } from 'react';

import { InlineError } from '@/components/app/states';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

/** Label + control + optional hint and error, wired by id. */
export function Field({
  id,
  label,
  hint,
  error,
  optional,
  children,
  className,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label htmlFor={id}>
        {label}
        {optional ? <span className="text-muted-foreground font-normal">optional</span> : null}
      </Label>
      {children}
      {error ? (
        <InlineError>{error}</InlineError>
      ) : hint ? (
        <p className="text-muted-foreground text-xs">{hint}</p>
      ) : null}
    </div>
  );
}

/** Roomier than the shadcn default, to match the pill buttons. */
export const inputClass = 'h-10 px-3.5';
