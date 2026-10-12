'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { FirebaseError } from 'firebase/app';
import {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
} from 'firebase/auth';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Logo } from '@/components/logo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth } from '@/lib/firebase';

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(6, 'Use at least 6 characters'),
});

type FormValues = z.infer<typeof schema>;

const ERROR_MESSAGES: Record<string, string> = {
  'auth/invalid-credential': 'That email and password do not match.',
  'auth/email-already-in-use': 'An account with that email already exists. Sign in instead.',
  'auth/weak-password': 'Choose a stronger password.',
  'auth/too-many-requests': 'Too many attempts. Wait a minute and try again.',
  'auth/popup-blocked': 'Your browser blocked the sign-in window. Allow pop-ups and try again.',
  'auth/network-request-failed': 'Network problem. Check your connection and try again.',
};

// Closing the Google window is a choice, not an error worth a toast.
const SILENT_ERRORS = new Set(['auth/popup-closed-by-user', 'auth/cancelled-popup-request']);

function reportAuthError(error: unknown) {
  const code = error instanceof FirebaseError ? error.code : '';
  if (SILENT_ERRORS.has(code)) return;
  toast.error(ERROR_MESSAGES[code] ?? 'Something went wrong. Please try again.');
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in');
  const [googlePending, setGooglePending] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!loading && user) router.replace('/app');
  }, [loading, user, router]);

  async function onSubmit({ email, password }: FormValues) {
    try {
      if (mode === 'sign-in') {
        await signInWithEmailAndPassword(firebaseAuth, email, password);
      } else {
        await createUserWithEmailAndPassword(firebaseAuth, email, password);
      }
    } catch (error) {
      reportAuthError(error);
    }
  }

  async function handleGoogle() {
    setGooglePending(true);
    try {
      await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
    } catch (error) {
      reportAuthError(error);
    } finally {
      setGooglePending(false);
    }
  }

  const isSignIn = mode === 'sign-in';
  const busy = isSubmitting || googlePending;

  return (
    <div className="flex min-h-svh flex-col items-center justify-center px-4 py-10">
      <Link href="/" className="mb-8">
        <Logo />
      </Link>

      <div className="bg-card w-full max-w-sm rounded-2xl border p-7 shadow-xl shadow-black/5">
        <h1 className="text-2xl font-medium tracking-[-0.03em]">
          {isSignIn ? 'Welcome back' : 'Create your account'}
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {isSignIn
            ? 'Sign in to pick up your job hunt.'
            : 'One profile for every application you send.'}
        </p>

        <Button
          variant="outline"
          size="lg"
          className="mt-6 h-10 w-full"
          onClick={handleGoogle}
          disabled={busy}
        >
          <GoogleMark />
          Continue with Google
        </Button>

        <div className="text-muted-foreground my-5 flex items-center gap-3 text-xs">
          <span className="bg-border h-px flex-1" />
          or
          <span className="bg-border h-px flex-1" />
        </div>

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              className="h-10 px-3.5"
              aria-invalid={!!errors.email}
              {...register('email')}
            />
            {errors.email ? (
              <p className="text-destructive text-xs">{errors.email.message}</p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete={isSignIn ? 'current-password' : 'new-password'}
              className="h-10 px-3.5"
              aria-invalid={!!errors.password}
              {...register('password')}
            />
            {errors.password ? (
              <p className="text-destructive text-xs">{errors.password.message}</p>
            ) : null}
          </div>

          <Button type="submit" size="lg" className="mt-1 h-10 w-full" disabled={busy}>
            {isSignIn ? 'Sign in' : 'Create account'}
          </Button>
        </form>
      </div>

      <p className="text-muted-foreground mt-6 text-sm">
        {isSignIn ? 'New to Rolesetu?' : 'Already have an account?'}{' '}
        <button
          type="button"
          className="text-primary font-medium underline-offset-4 hover:underline"
          onClick={() => setMode(isSignIn ? 'sign-up' : 'sign-in')}
        >
          {isSignIn ? 'Create an account' : 'Sign in'}
        </button>
      </p>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="size-4">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}
