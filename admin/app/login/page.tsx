'use client';

import { GoogleAuthProvider, signInWithPopup, signOut } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { errorMessage } from '@/lib/api';
import { firebaseAuth } from '@/lib/firebase';
import { useAdmin, useGoogleAccount } from '@/lib/session';

export default function LoginPage() {
  const router = useRouter();
  const account = useGoogleAccount();
  const admin = useAdmin(account?.uid ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (admin.isSuccess) router.replace('/');
  }, [admin.isSuccess, router]);

  async function signIn() {
    setBusy(true);
    setError(null);
    try {
      await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
    } catch (e) {
      const message = e instanceof Error ? e.message : '';
      setError(message.includes('popup-closed') ? null : 'Could not sign in. Try again.');
    } finally {
      setBusy(false);
    }
  }

  // Signed in with Google, but the API says this account is not an admin.
  const refused = account && admin.isError;

  return (
    <main className="flex min-h-dvh items-center justify-center bg-zinc-100 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-sm ring-1 ring-zinc-200">
        <p className="text-xs font-bold tracking-widest text-blue-600 uppercase">Rolesetu</p>
        <h1 className="mt-1 text-2xl font-black text-zinc-900">Admin panel</h1>
        <p className="mt-2 text-sm text-zinc-500">Sign in with an admin Google account.</p>
        <button
          onClick={signIn}
          disabled={busy || admin.isFetching}
          className="mt-6 w-full rounded-lg bg-zinc-900 px-4 py-3 text-sm font-bold text-white hover:bg-black disabled:opacity-60"
        >
          {busy || admin.isFetching ? 'Signing in…' : 'Continue with Google'}
        </button>
        {refused ? (
          <div className="mt-4 text-sm" role="alert">
            <p className="font-medium text-red-700">{errorMessage(admin.error)}</p>
            <p className="mt-1 text-zinc-500">
              Signed in as {account.email}. An admin is an email listed in ADMIN_EMAILS on the API.
            </p>
            <button
              onClick={() => signOut(firebaseAuth)}
              className="mt-2 font-semibold text-zinc-700 underline hover:text-black"
            >
              Use a different account
            </button>
          </div>
        ) : error ? (
          <p className="mt-3 text-sm font-medium text-red-700" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </main>
  );
}
