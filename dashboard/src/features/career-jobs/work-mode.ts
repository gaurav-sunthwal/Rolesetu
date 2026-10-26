import { Building, House, Laptop, type LucideIcon } from 'lucide-react';

import type { WorkMode } from '@/lib/api/types';

export const WORK_MODE_META: Record<WorkMode, { label: string; icon: LucideIcon | null }> = {
  remote: { label: 'Remote', icon: House },
  hybrid: { label: 'Hybrid', icon: Laptop },
  onsite: { label: 'On-site', icon: Building },
  not_stated: { label: 'Not stated', icon: null },
};

/** The order the filter lists them in, whatever their counts. */
export const WORK_MODE_ORDER: readonly WorkMode[] = ['remote', 'hybrid', 'onsite', 'not_stated'];
