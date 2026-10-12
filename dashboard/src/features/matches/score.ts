import type { Verdict } from '@/lib/api/types';

export type ScoreBand = { label: string; stroke: string; text: string };

/** Display only: the score itself is always computed by the API. */
export function bandOf(score: number): ScoreBand {
  if (score >= 75) return { label: 'Strong fit', stroke: 'stroke-success', text: 'text-success' };
  if (score >= 50) return { label: 'Worth a shot', stroke: 'stroke-primary', text: 'text-primary' };
  return { label: 'A stretch', stroke: 'stroke-warning', text: 'text-foreground' };
}

export const VERDICT_META: Record<Verdict, { label: string; dot: string }> = {
  strong: { label: 'Strong', dot: 'bg-success' },
  partial: { label: 'Partial', dot: 'bg-warning' },
  missing: { label: 'Missing', dot: 'bg-destructive' },
};
