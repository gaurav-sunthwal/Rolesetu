'use client';

import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';

/** Primary call to action: sends signed-in visitors to the app, everyone else to sign-up. */
export function LandingCta({ size = 'hero' }: { size?: 'hero' | 'nav' }) {
  const { user } = useAuth();
  const href = user ? '/app' : '/login';

  return (
    <Button
      nativeButton={false}
      render={<Link href={href} />}
      className={cn(size === 'hero' ? 'h-12 px-7 text-base' : 'h-9 px-4')}
    >
      {user ? 'Open dashboard' : 'Get started'}
    </Button>
  );
}

export function LandingLoginLink() {
  const { user } = useAuth();
  if (user) return null;

  return (
    <Button
      nativeButton={false}
      render={<Link href="/login" />}
      variant="outline"
      className="bg-background hidden h-9 px-4 sm:inline-flex"
    >
      Log in
    </Button>
  );
}
