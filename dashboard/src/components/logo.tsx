import { cn } from '@/lib/utils';

export function Logo({ className, hideWordmark }: { className?: string; hideWordmark?: boolean }) {
  return (
    <span className={cn('flex items-center gap-2', className)}>
      {/* An R whose lower half is a bridge arch: "setu" means bridge. */}
      <svg
        viewBox="0 0 64 64"
        className="size-7 shrink-0"
        role={hideWordmark ? 'img' : undefined}
        aria-label={hideWordmark ? 'Rolesetu' : undefined}
        aria-hidden={hideWordmark ? undefined : true}
      >
        <rect width="64" height="64" rx="15" className="fill-primary" />
        <g fill="none" strokeWidth="7" strokeLinejoin="round" className="stroke-primary-foreground">
          <path d="M21.5 48V19.5h12.75a8.25 8.25 0 0 1 0 16.5H21.5" />
          <path d="M21.5 48v-1.5a10.5 10.5 0 0 1 21 0V48" />
        </g>
      </svg>
      {hideWordmark ? null : (
        <span className="text-base font-semibold tracking-[-0.02em]">Rolesetu</span>
      )}
    </span>
  );
}
