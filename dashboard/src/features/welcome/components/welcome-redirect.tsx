'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { useProfile } from '@/features/profile/hooks';
import { isProfileEmpty, isWelcomeDone, WELCOME_FROM } from '@/features/welcome/state';
import { useAuth } from '@/lib/auth-context';

/**
 * Sends someone with an empty profile to the setup, from the pages sign-in and
 * the extension's "Connect" button land on. Renders nothing.
 */
export function WelcomeRedirect() {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const profile = useProfile();

  const shouldGo =
    user !== null &&
    WELCOME_FROM.has(pathname) &&
    profile.data !== undefined &&
    isProfileEmpty(profile.data) &&
    !isWelcomeDone(user.uid);

  useEffect(() => {
    if (shouldGo) router.replace('/app/welcome');
  }, [shouldGo, router]);

  return null;
}
