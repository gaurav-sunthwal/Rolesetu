import { cn } from '@/lib/utils';

export function Logo({ className, hideWordmark }: { className?: string; hideWordmark?: boolean }) {
  return (
    <span className={cn('flex items-center gap-2', className)}>
      <span className="bg-primary text-primary-foreground flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-bold">
        R
      </span>
      {hideWordmark ? null : (
        <span className="text-base font-semibold tracking-[-0.02em]">Rolesetu</span>
      )}
    </span>
  );
}
