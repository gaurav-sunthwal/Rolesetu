import { STATUS_META } from '@/features/applications/status';
import type { ApplicationStatus } from '@/lib/api/types';
import { cn } from '@/lib/utils';

export function StatusDot({
  status,
  className,
}: {
  status: ApplicationStatus;
  className?: string;
}) {
  return (
    <span className={cn('size-2 shrink-0 rounded-full', STATUS_META[status].dot, className)} />
  );
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className="bg-secondary inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
      <StatusDot status={status} />
      {STATUS_META[status].label}
    </span>
  );
}
