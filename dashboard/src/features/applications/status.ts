import type { ApplicationStatus } from '@/lib/api/types';

export const STATUSES = [
  'saved',
  'applied',
  'replied',
  'interview',
  'offer',
  'rejected',
] as const satisfies readonly ApplicationStatus[];

export const STATUS_META: Record<ApplicationStatus, { label: string; dot: string }> = {
  saved: { label: 'Saved', dot: 'bg-muted-foreground/60' },
  applied: { label: 'Applied', dot: 'bg-primary' },
  replied: { label: 'Replied', dot: 'bg-warning' },
  interview: { label: 'Interview', dot: 'bg-violet-500' },
  offer: { label: 'Offer', dot: 'bg-success' },
  rejected: { label: 'Rejected', dot: 'bg-destructive' },
};

export const STATUS_ITEMS = STATUSES.map((value) => ({ value, label: STATUS_META[value].label }));
