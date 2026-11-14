import type { Metadata } from 'next';

import { PlanPage } from '@/features/billing/components/plan-page';

export const metadata: Metadata = { title: 'Plan & invites' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <PlanPage />;
}
