'use client';

import { signOut } from 'firebase/auth';
import { Download, LogOut, Monitor, Moon, Sun } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { Suspense } from 'react';
import { toast } from 'sonner';

import { SectionCard } from '@/components/app/section-card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PlanCard } from '@/features/billing/components/plan-card';
import { GmailCard } from '@/features/inbox/components/gmail-card';
import { ExtensionCard } from '@/features/settings/components/extension-card';
import { useExportData } from '@/features/settings/hooks';
import { errorMessage } from '@/lib/api/client';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth } from '@/lib/firebase';
import { cn } from '@/lib/utils';

export function SettingsPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <AccountCard />
      <PlanCard />
      <AppearanceCard />
      <ExtensionCard />
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
