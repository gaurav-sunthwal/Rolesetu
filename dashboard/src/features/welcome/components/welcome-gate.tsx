'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { useProfile } from '@/features/profile/hooks';
import {
  isProfileEmpty,
  isWelcomeDone,
  markWelcomeDone,
  WELCOME_FROM,
} from '@/features/welcome/state';
import { useAuth } from '@/lib/auth-context';

/**
 * Sends someone with an empty profile to the setup, from the pages sign-in and
 * the extension's "Connect" button land on.
 *
 * On those pages it holds back the dashboard until it knows, so a new user goes
 * straight to the setup instead of seeing the dashboard first and then being
 * moved. Once a browser has seen this account with a profile (or the setup
 * finished or skipped), it lets every page through at once from then on.
 */
export function WelcomeGate({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const done = user !== null && isWelcomeDone(user.uid);
  const watching = user !== null && !done && WELCOME_FROM.has(pathname);
  const profile = useProfile();

  const empty = profile.data !== undefined && isProfileEmpty(profile.data);
  const shouldGo = watching && empty;

  useEffect(() => {
    // Fetched while the profile loads, so the move itself is instant.
    if (watching) router.prefetch('/app/welcome');
  }, [watching, router]);

  useEffect(() => {
    if (shouldGo) router.replace('/app/welcome');
  }, [shouldGo, router]);

  useEffect(() => {
    // Someone with a profile never needs the setup: stop waiting for it here.
    if (user && profile.data !== undefined && !isProfileEmpty(profile.data)) {
      markWelcomeDone(user.uid);
    }
  }, [user, profile.data]);

  // Still deciding, or on the way to the setup. A failed load lets the page
  // through, where it shows its own error.
  if (watching && (profile.isPending || shouldGo)) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-3" role="status">
        <div className="border-muted-foreground/30 border-t-primary size-6 animate-spin rounded-full border-2 motion-reduce:animate-none" />
        <p className="text-muted-foreground text-sm">Getting your account ready…</p>
      </div>
    );
  }
  return children;
}
