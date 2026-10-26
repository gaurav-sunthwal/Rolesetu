'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { FirebaseError } from 'firebase/app';
import {
  createUserWithEmailAndPassword,
  getAdditionalUserInfo,
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
} from 'firebase/auth';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Logo } from '@/components/logo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { readPendingJob } from '@/features/preview/pending-job';
import { applyResume, uploadResume } from '@/features/resume/api';
import { type ReadResume, ResumeStart } from '@/features/resume-signup/components/resume-start';
import { errorMessage } from '@/lib/api/client';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth } from '@/lib/firebase';

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(6, 'Use at least 6 characters'),
});

type FormValues = z.infer<typeof schema>;

const ERROR_MESSAGES: Record<string, string> = {
  'auth/invalid-credential':
    'That email and password do not match. If you signed up with Google, use Continue with Google.',
  'auth/email-already-in-use': 'An account with that email already exists. Sign in instead.',
  'auth/weak-password': 'Choose a stronger password.',
  'auth/too-many-requests': 'Too many attempts. Wait a minute and try again.',
  'auth/popup-blocked': 'Your browser blocked the sign-in window. Allow pop-ups and try again.',
  'auth/network-request-failed': 'Network problem. Check your connection and try again.',
};

// Closing the Google window is a choice, not an error worth a toast.
const SILENT_ERRORS = new Set(['auth/popup-closed-by-user', 'auth/cancelled-popup-request']);

function codeOf(error: unknown): string {
  return error instanceof FirebaseError ? error.code : '';
}

function reportAuthError(error: unknown) {
  const code = codeOf(error);
  if (SILENT_ERRORS.has(code)) return;
  toast.error(ERROR_MESSAGES[code] ?? 'Something went wrong. Please try again.');
}

/**
 * Where to go once signed in: the job looked up on the landing page, else the
 * page that sent the visitor here, else the dashboard. Only dashboard paths are
 * followed, so a crafted link cannot send anyone off the site.
 */
function afterSignIn(): string {
  if (readPendingJob()) return '/app/check';
  const next = new URLSearchParams(window.location.search).get('next');
  return next && /^\/app(\/[\w-]+)*$/.test(next) ? next : '/app';
}

type Mode = 'start' | 'resume' | 'sign-in' | 'sign-up';

export default function LoginPage() {
  // Reading the link's `next` needs a Suspense boundary. The fallback is the
  // usual first screen, so the page is drawn straight away rather than blank.
  return (
    <Suspense fallback={<Login initialMode="start" />}>
      <LoginFromLink />
    </Suspense>
  );
}

function LoginFromLink() {
  // Someone sent here from inside the app (an expired session) wants to log
  // in; everyone else starts with their resume. That includes people the
  // extension sent right after install: most of them have no account yet.
  const params = useSearchParams();
  const returning = params.has('next') && params.get('from') !== 'extension';
  return <Login initialMode={returning ? 'sign-in' : 'start'} />;
}

function Login({ initialMode }: { initialMode: Mode }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [read, setRead] = useState<ReadResume | null>(null);
  // The email that turned out to have an account, so the form logs in to it.
  const [existingEmail, setExistingEmail] = useState<string | null>(null);
  const [googlePending, setGooglePending] = useState(false);
  const [savingResume, setSavingResume] = useState(false);
  // While a resume is being saved after sign-in, this page does the redirect
  // itself once the profile is filled, not the moment the account exists.
  const holdRedirect = useRef(false);

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!loading && user && !holdRedirect.current) router.replace(afterSignIn());
  }, [loading, user, router]);

  useEffect(() => {
    // Load where sign-in leads while the person types, so arriving is instant.
    router.prefetch('/app');
    router.prefetch('/app/welcome');
  }, [router]);

  function showResume(next: ReadResume) {
    setRead(next);
    setExistingEmail(null);
    reset({ email: next.identity.email ?? '', password: '' });
    setMode('resume');
  }

  function switchTo(next: Mode) {
    setRead(null);
    setExistingEmail(null);
    setMode(next);
  }

  /** Signed in: save the resume, fill the profile from it, then move on. */
  async function saveResume(file: File, isNewUser: boolean) {
    setSavingResume(true);
    try {
      const resume = await uploadResume(file, () => undefined);
      // Merge fills an empty profile completely and keeps a returning user's edits.
      await applyResume(resume.id, 'merge');
      toast.success(
        isNewUser
          ? 'Your profile is ready. We filled it in from your resume.'
          : 'Your profile was updated from your resume.',
      );
      // New accounts check what was read; the setup lets them skip it.
      router.replace(isNewUser && !readPendingJob() ? '/app/welcome' : afterSignIn());
    } catch (error) {
      toast.error(
        `You're signed in, but your resume was not saved: ${errorMessage(error)} Upload it again here.`,
      );
      router.replace(isNewUser ? '/app/welcome' : '/app/profile');
    }
  }

  async function onSubmit({ email, password }: FormValues) {
    if (mode === 'resume' && read) {
      holdRedirect.current = true;
      try {
        if (existingEmail === email) {
          await signInWithEmailAndPassword(firebaseAuth, email, password);
          await saveResume(read.file, false);
          return;
        }
        try {
          await createUserWithEmailAndPassword(firebaseAuth, email, password);
        } catch (error) {
          if (codeOf(error) !== 'auth/email-already-in-use') throw error;
          holdRedirect.current = false;
          setExistingEmail(email);
          return;
        }
        await saveResume(read.file, true);
      } catch (error) {
        holdRedirect.current = false;
        reportAuthError(error);
      }
      return;
    }

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
    if (read) holdRedirect.current = true;
    try {
      const credential = await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
      if (read) await saveResume(read.file, getAdditionalUserInfo(credential)?.isNewUser ?? false);
    } catch (error) {
      holdRedirect.current = false;
      reportAuthError(error);
    } finally {
      setGooglePending(false);
    }
  }

  const busy = isSubmitting || googlePending || savingResume;
  const typedEmail = useWatch({ control, name: 'email' });
  const isExisting = existingEmail !== null && existingEmail === typedEmail;

  if (savingResume) {
    return (
      <Shell>
        <div className="flex flex-col items-center gap-3 py-8 text-center" role="status">
          <span className="border-muted-foreground/30 border-t-primary size-6 animate-spin rounded-full border-2 motion-reduce:animate-none" />
          <p className="font-medium">Building your profile…</p>
          <p className="text-muted-foreground text-sm">
            Adding your skills, roles, projects and education from your resume.
          </p>
        </div>
      </Shell>
    );
  }

  const google = (
    <Button
      variant="outline"
      size="lg"
      className="h-10 w-full"
      onClick={handleGoogle}
      disabled={busy}
    >
      <GoogleMark />
      Continue with Google
    </Button>
  );

  if (mode === 'start') {
    return (
      <Shell
        footer={
          <>
            <p>
              Already have an account?{' '}
              <TextButton onClick={() => switchTo('sign-in')}>Log in</TextButton>
            </p>
            <p className="mt-2 text-xs">
              <TextButton onClick={() => switchTo('sign-up')}>
                Sign up with email instead
              </TextButton>
            </p>
          </>
        }
      >
        <h1 className="text-2xl font-medium tracking-[-0.03em]">Get started</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Upload your resume once. We build your profile and score every job against it.
        </p>
        <div className="mt-6">
          <ResumeStart onRead={showResume} />
        </div>
        <Divider />
        {google}
      </Shell>
    );
  }

  const isResume = mode === 'resume' && read !== null;
  const isSignIn = mode === 'sign-in' || isExisting;
  const firstName = read?.identity.first_name;
  const foundEmail = read?.identity.email;

  return (
    <Shell
      footer={
        isResume ? (
          <p>
            Wrong file?{' '}
            <TextButton onClick={() => switchTo('start')}>Use a different resume</TextButton>
          </p>
        ) : mode === 'sign-in' ? (
          <p>
            New to Rolesetu?{' '}
            <TextButton onClick={() => switchTo('start')}>Start with your resume</TextButton>
          </p>
        ) : (
          <p>
            Already have an account?{' '}
            <TextButton onClick={() => switchTo('sign-in')}>Sign in</TextButton>
          </p>
        )
      }
    >
      <h1 className="text-2xl font-medium tracking-[-0.03em]">
        {isResume
          ? isExisting
            ? `Welcome back${firstName ? `, ${firstName}` : ''}`
            : firstName
              ? `Hi ${firstName} 👋`
              : 'Almost there'
          : isSignIn
            ? 'Welcome back'
            : 'Create your account'}
      </h1>
      <p className="text-muted-foreground mt-1 text-sm">
        {isResume
          ? isExisting
            ? 'You already have an account with this email. Log in and we will update your profile from this resume.'
            : 'Choose a password to save your profile, so it is here next time.'
          : isSignIn
            ? 'Sign in to pick up your job hunt.'
            : 'One profile for every application you send.'}
      </p>

      {isResume ? null : (
        <>
          <div className="mt-6">{google}</div>
          <Divider />
        </>
      )}

      <form
        onSubmit={(event) => void handleSubmit(onSubmit)(event)}
        noValidate
        className={isResume ? 'mt-6 flex flex-col gap-4' : 'flex flex-col gap-4'}
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            className="h-10 px-3.5"
            aria-invalid={!!errors.email}
            aria-describedby={isResume ? 'email-hint' : undefined}
            {...register('email')}
          />
          {errors.email ? (
            <p className="text-destructive text-xs">{errors.email.message}</p>
          ) : isResume ? (
            <p id="email-hint" className="text-muted-foreground text-xs">
              {foundEmail
                ? 'Found on your resume. Change it if you use a different one.'
                : 'We could not find an email on your resume. Enter the one you use.'}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">
            {isResume && !isExisting ? 'Choose a password' : 'Password'}
          </Label>
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
          {isResume
            ? isExisting
              ? 'Log in and update my profile'
              : 'Save my profile'
            : isSignIn
              ? 'Sign in'
              : 'Create account'}
        </Button>
      </form>

      {isResume ? (
        <>
          <Divider />
          {google}
        </>
      ) : null}
    </Shell>
  );
}

function Shell({ children, footer }: { children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center px-4 py-10">
      <Link href="/" className="mb-8">
        <Logo />
      </Link>
      <div className="bg-card w-full max-w-sm rounded-2xl border p-7 shadow-xl shadow-black/5">
        {children}
      </div>
      {footer ? (
        <div className="text-muted-foreground mt-6 text-center text-sm">{footer}</div>
      ) : null}
    </div>
  );
}

function Divider() {
  return (
    <div className="text-muted-foreground my-5 flex items-center gap-3 text-xs">
      <span className="bg-border h-px flex-1" />
      or
      <span className="bg-border h-px flex-1" />
    </div>
  );
}

function TextButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      className="text-primary font-medium underline-offset-4 hover:underline"
      onClick={onClick}
    >
      {children}
    </button>
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
