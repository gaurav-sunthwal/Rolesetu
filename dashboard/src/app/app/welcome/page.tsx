import type { Metadata } from 'next';

import { WelcomePage } from '@/features/welcome/components/welcome-page';

export const metadata: Metadata = { title: 'Welcome' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <WelcomePage />;
}
