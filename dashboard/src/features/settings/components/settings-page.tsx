'use client';

import { signOut } from 'firebase/auth';
import { Download, KeyRound, LogOut, Monitor, Moon, Sun } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { Suspense, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { Field, inputClass } from '@/components/app/field';
import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { GmailCard } from '@/features/inbox/components/gmail-card';
import { ExtensionCard } from '@/features/settings/components/extension-card';
import {
  useDeleteLlmKey,
  useExportData,
  useLlmKeyStatus,
  useSaveLlmKey,
} from '@/features/settings/hooks';
import { errorMessage } from '@/lib/api/client';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth } from '@/lib/firebase';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

export function SettingsPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <AccountCard />
      <AppearanceCard />
      <ExtensionCard />
      <LlmKeyCard />
      {/* Reads the address bar after the trip to Google, which needs a Suspense boundary. */}
      <Suspense fallback={<Skeleton className="h-24 w-full rounded-3xl" />}>
        <GmailCard />
      </Suspense>
      <DataCard />
    </div>
  );
}

function AccountCard() {
  const router = useRouter();
  const { user } = useAuth();
  const email = user?.email ?? '';
  const name = user?.displayName || email.split('@')[0] || 'Your account';
  const viaGoogle = user?.providerData.some((provider) => provider.providerId === 'google.com');

  async function handleSignOut() {
    try {
      await signOut(firebaseAuth);
      router.replace('/');
    } catch {
      toast.error('Could not sign out. Please try again.');
    }
  }

  return (
    <SectionCard title="Account">
      <div className="flex flex-wrap items-center gap-4">
        <Avatar className="size-12">
          {user?.photoURL ? <AvatarImage src={user.photoURL} alt="" /> : null}
          <AvatarFallback className="bg-primary/10 text-primary font-semibold uppercase">
            {name.charAt(0)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{name}</p>
          <p className="text-muted-foreground truncate text-sm">
            {email}
            {viaGoogle ? ' · Signed in with Google' : ''}
          </p>
        </div>
        <Button variant="outline" onClick={handleSignOut}>
          <LogOut />
          Sign out
        </Button>
      </div>
    </SectionCard>
  );
}

const THEMES = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
] as const;

function AppearanceCard() {
  const { theme, setTheme } = useTheme();

  return (
    <SectionCard title="Appearance" description="System follows your device setting.">
      <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-2 sm:max-w-sm">
        {THEMES.map((option) => {
          const active = theme === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setTheme(option.value)}
              className={cn(
                'focus-visible:ring-ring/50 flex flex-col items-center gap-2 rounded-2xl border px-3 py-4 text-sm font-medium transition-colors outline-none focus-visible:ring-3',
                active
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <option.icon className="size-5" />
              {option.label}
            </button>
          );
        })}
      </div>
    </SectionCard>
  );
}

function LlmKeyCard() {
  const status = useLlmKeyStatus();
  const save = useSaveLlmKey();
  const remove = useDeleteLlmKey();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [confirmingRemove, setConfirmingRemove] = useState(false);

  function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed.length < 10) return setError('That does not look like a full API key');
    setError(null);
    save.mutate(trimmed, {
      onSuccess: () => {
        setValue('');
        toast.success('Key tested with Google and saved');
      },
      // Shown on the field, not as a toast: the fix is to correct what was pasted.
      onError: (failure) => setError(errorMessage(failure)),
    });
  }

  return (
    <SectionCard
      title="Your own Gemini key"
      description="Optional. Job checks and resume reading run without AI, so no key is needed for them. This is kept for AI features such as tailored resumes and emails."
    >
      {status.isPending ? (
        <Skeleton className="h-10 w-full" />
      ) : status.isError ? (
        <ErrorState error={status.error} onRetry={() => status.refetch()} className="py-6" />
      ) : (
        <div className="flex flex-col gap-4">
          {status.data.has_key ? (
            <div className="bg-secondary flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3">
              <KeyRound className="text-success size-4 shrink-0" />
              <p className="min-w-0 flex-1 text-sm">
                <span className="font-medium">A key is saved.</span>{' '}
                <span className="text-muted-foreground">
                  {status.data.updated_at ? `Updated ${formatDate(status.data.updated_at)}. ` : ''}
                  It is stored encrypted and never shown again.
                </span>
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => setConfirmingRemove(true)}
              >
                Remove
              </Button>
            </div>
          ) : null}

          <form
            onSubmit={handleSave}
            noValidate
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
          >
            <Field
              id="llm-key"
              label={status.data.has_key ? 'Replace it with a new key' : 'API key'}
              error={error ?? undefined}
              className="flex-1"
            >
              <Input
                id="llm-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                className={inputClass}
                placeholder="Paste your Gemini API key"
                aria-invalid={!!error}
                disabled={save.isPending}
                value={value}
                onChange={(event) => {
                  setValue(event.target.value);
                  setError(null);
                }}
              />
            </Field>
            <Button type="submit" className="h-10" disabled={!value.trim() || save.isPending}>
              {save.isPending ? 'Testing key…' : 'Test and save'}
            </Button>
          </form>
          <p className="text-muted-foreground text-xs">
            Create a key in{' '}
            <a
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noreferrer"
              className="text-primary font-medium underline-offset-4 hover:underline"
            >
              Google AI Studio
            </a>
            . We test the key with Google before saving it. Usage on your key is billed to your
            Google account.
          </p>
        </div>
      )}

      <ConfirmDialog
        open={confirmingRemove}
        onOpenChange={setConfirmingRemove}
        title="Remove your Gemini key?"
        description="AI features will use Rolesetu's own keys. You can add a key again at any time."
        confirmLabel={remove.isPending ? 'Removing…' : 'Remove key'}
        pending={remove.isPending}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setConfirmingRemove(false);
              toast.success('Key removed');
            },
            onError: (failure) => toast.error(errorMessage(failure)),
          })
        }
      />
    </SectionCard>
  );
}

function DataCard() {
  const exportData = useExportData();

  function handleExport() {
    exportData.mutate(undefined, {
      onSuccess: (data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `rolesetu-export-${data.exported_at.slice(0, 10)}.json`;
        link.click();
        URL.revokeObjectURL(url);
        toast.success('Export downloaded');
      },
      onError: (failure) => toast.error(errorMessage(failure)),
    });
  }

  return (
    <SectionCard
      title="Your data"
      description="Download your profile, saved answers, applications and recent job checks as a JSON file."
    >
      <Button variant="outline" onClick={handleExport} disabled={exportData.isPending}>
        <Download />
        {exportData.isPending ? 'Preparing…' : 'Export my data'}
      </Button>
    </SectionCard>
  );
}
