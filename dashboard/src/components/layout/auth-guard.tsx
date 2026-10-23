'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { useAuth } from '@/lib/auth-context';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Remember the page, so signing in returns to it (the extension opens Settings, for one).
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  if (loading || !user) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <div className="border-muted-foreground/30 border-t-primary size-6 animate-spin rounded-full border-2" />
      </div>
    );
  }

  return children;
}
