import type { Metadata } from 'next';

import { JobsPage } from '@/features/career-jobs/components/jobs-page';

export const metadata: Metadata = { title: 'Fresh jobs' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <JobsPage />;
}
