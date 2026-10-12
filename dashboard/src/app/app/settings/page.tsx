import type { Metadata } from 'next';

import { SettingsPage } from '@/features/settings/components/settings-page';

export const metadata: Metadata = { title: 'Settings' };

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <SettingsPage />;
}
