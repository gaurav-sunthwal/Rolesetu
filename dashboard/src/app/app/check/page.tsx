import type { Metadata } from 'next';

import { CheckPage } from '@/features/matches/components/check-page';

export const metadata: Metadata = { title: 'Check a job' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <CheckPage />;
}
