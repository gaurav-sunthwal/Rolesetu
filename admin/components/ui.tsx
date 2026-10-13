import type { ReactNode } from 'react';

const TONES = {
  zinc: 'bg-zinc-100 text-zinc-700',
  green: 'bg-emerald-100 text-emerald-800',
  amber: 'bg-amber-100 text-amber-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-sky-100 text-sky-800',
} as const;

export function Badge({
  children,
  tone = 'zinc',
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-black tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl bg-white shadow-sm ring-1 ring-zinc-200 ${className}`}>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-10 text-center text-sm text-zinc-500">{children}</p>;
}

/** A block of grey bars shown while a table or card is loading. */
export function Loading({ rows = 5 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-3 p-4">
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="h-5 animate-pulse rounded bg-zinc-100 motion-reduce:animate-none"
        />
      ))}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="px-4 py-10 text-center">
      <p className="text-sm font-semibold text-red-700">This did not load</p>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className={`${button} mt-4`}>
          Try again
        </button>
      )}
    </div>
  );
}

export function LoadMore({
  show,
  busy,
  onClick,
}: {
  show: boolean;
  busy: boolean;
  onClick: () => void;
}) {
  if (!show) return null;
  return (
    <div className="border-t border-zinc-200 px-4 py-3 text-center">
      <button onClick={onClick} disabled={busy} className={button}>
        {busy ? 'Loading…' : 'Load more'}
      </button>
    </div>
  );
}

export const th =
  'px-4 py-2.5 text-left text-xs font-semibold tracking-wide text-zinc-500 uppercase';
export const td = 'px-4 py-3 align-middle';
export const button =
  'rounded-lg bg-white px-3 py-1.5 text-sm font-semibold ring-1 ring-zinc-200 hover:bg-zinc-50 disabled:opacity-60';
