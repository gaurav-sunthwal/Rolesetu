'use client';

import { useQueryClient } from '@tanstack/react-query';
import { signOut } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { NavLinks } from '@/components/NavLinks';
import { firebaseAuth } from '@/lib/firebase';
import { useAdmin, useGoogleAccount } from '@/lib/session';

/**
 * Every panel page sits behind this: a signed-in Google account that the API
 * confirms is an admin. It is a convenience for the person, not the lock: the
 * API refuses every admin request from anyone else regardless.
 */
export default function PanelLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const account = useGoogleAccount();
  const admin = useAdmin(account?.uid ?? null);
  const turnedAway = account === null || admin.isError;

  useEffect(() => {
    if (turnedAway) router.replace('/login');
  }, [turnedAway, router]);

  if (!admin.data) {
    return (
      <div
        className="flex min-h-dvh items-center justify-center"
        role="status"
        aria-label="Loading"
      >
        <div className="size-6 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 motion-reduce:animate-none" />
      </div>
    );
  }

  async function leave() {
    await signOut(firebaseAuth);
    queryClient.clear();
  }

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="flex shrink-0 flex-col border-b border-zinc-200 bg-white px-4 py-6 md:sticky md:top-0 md:h-dvh md:w-60 md:border-r md:border-b-0">
        <p className="px-2 text-xs font-bold tracking-widest text-blue-600 uppercase">Rolesetu</p>
        <p className="px-2 text-lg font-black">Admin</p>
        <NavLinks />
        <div className="mt-6 border-t border-zinc-200 px-2 pt-4 md:mt-auto">
          <p className="truncate text-xs text-zinc-500" title={admin.data.email}>
            {admin.data.email}
          </p>
          <button
            onClick={leave}
            className="mt-2 text-sm font-semibold text-zinc-700 hover:text-black"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-8 md:px-8">{children}</main>
    </div>
  );
}
