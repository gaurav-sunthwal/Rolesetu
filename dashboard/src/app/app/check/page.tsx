import { CheckPage } from '@/features/matches/components/check-page';

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function Page() {
  return <CheckPage />;
}
