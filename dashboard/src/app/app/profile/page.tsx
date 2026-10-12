import type { Metadata } from 'next';

import { ProfilePage } from '@/features/profile/components/profile-page';

export const metadata: Metadata = { title: 'Profile' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <ProfilePage />;
}
