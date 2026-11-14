'use client';

import { useQuery } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';

import { api } from '@/lib/api/client';
import type { Credits } from '@/lib/api/types';
import { formatDate } from '@/lib/format';

export const creditsKey = ['billing', 'credits'] as const;

async function getCredits(): Promise<Credits> {
  const { data } = await api.get<Credits>('/credits/me');
  return data;
}

export function useCredits() {
  return useQuery({ queryKey: creditsKey, queryFn: getCredits, staleTime: 30_000 });
}

/** This month's AI credits as a bar: what is left, and when they come back. */
export function CreditsMeter() {
  const credits = useCredits();
  if (credits.isPending) {
    return <div className="bg-muted h-12 animate-pulse rounded-2xl" aria-hidden />;
  }
  if (credits.isError) return null; // the plan card still says what matters
  const { left, limit, resets_at: resetsAt, plan, pro_limit: proLimit } = credits.data;
  const share = limit > 0 ? Math.round((left / limit) * 100) : 0;

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 font-medium">
          <Sparkles className="text-primary size-4" aria-hidden />
          AI credits this month
        </span>
        <span className="text-muted-foreground">
          {left} of {limit} left · back on {formatDate(resetsAt)}
        </span>
      </div>
      <div
        className="bg-muted mt-3 h-2 overflow-hidden rounded-full"
        role="meter"
        aria-label="AI credits left this month"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={left}
      >
        <div
          className={left === 0 ? 'bg-destructive h-full' : 'bg-primary h-full'}
          style={{ width: `${share}%` }}
        />
      </div>
      <p className="text-muted-foreground mt-2 text-xs">
        An AI answer on a form or a resume assistant message uses 1 credit.
        {plan === 'free' ? ` Pro gives ${proLimit} a month.` : ''} Everything without AI is
        unlimited.
      </p>
    </div>
  );
}
