import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

/**
 * Light-on-black caustics image, screened over whatever colour sits behind it,
 * so one file tints to any panel.
 */
export function Texture({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 bg-[url('/textures/caustics.jpg')] bg-cover bg-center mix-blend-screen",
        className,
      )}
    />
  );
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        'bg-card inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[0.6875rem] leading-4 font-medium tracking-[0.14em] uppercase',
        className,
      )}
    >
      <span className="bg-primary size-2 rounded-full" />
      {children}
    </p>
  );
}

/** Display heading: medium weight and tight tracking instead of heavy bold. */
export function Display({
  as: Tag = 'h2',
  className,
  children,
}: {
  as?: 'h1' | 'h2';
  className?: string;
  children: ReactNode;
}) {
  return (
    <Tag
      className={cn(
        'text-4xl leading-[1.06] font-medium tracking-[-0.04em] text-balance sm:text-5xl',
        className,
      )}
    >
      {children}
    </Tag>
  );
}
