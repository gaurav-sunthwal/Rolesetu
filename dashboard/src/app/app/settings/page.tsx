import { SettingsPage } from '@/features/settings/components/settings-page';

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <SettingsPage />;
}
