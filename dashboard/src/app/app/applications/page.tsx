import type { Metadata } from 'next';

import { ApplicationsPage } from '@/features/applications/components/applications-page';

export const metadata: Metadata = { title: 'Applications' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <ApplicationsPage />;
}
