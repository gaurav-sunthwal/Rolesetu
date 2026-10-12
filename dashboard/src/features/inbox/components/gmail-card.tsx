'use client';

import { Loader2, Mail, RefreshCw } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { SectionCard } from '@/components/app/section-card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { getGmailConnectUrl } from '@/features/inbox/api';
import { useDisconnectGmail, useInboxSync } from '@/features/inbox/hooks';
import { errorMessage } from '@/lib/api/client';
import { timeAgo } from '@/lib/format';

// What Google's redirect back to this page reports, in the user's words.
const OUTCOMES: Record<string, { ok: boolean; message: string }> = {
  connected: { ok: true, message: 'Gmail connected. Reading your recent job mail now.' },
  denied: { ok: false, message: 'Gmail was not connected. Read access is needed to continue.' },
  expired: { ok: false, message: 'That took too long. Press Connect Gmail and try again.' },
  failed: { ok: false, message: 'Gmail could not be connected. Please try again.' },
  api_off: {
    ok: false,
    message:
      'Google accepted the sign-in, but the Gmail API is switched off for this app’s Google Cloud project. Enable “Gmail API” there, then connect again.',
  },
};

/** Connects, syncs and disconnects Gmail. Lives on Settings. */
export function GmailCard() {
  const router = useRouter();
  const outcome = useSearchParams().get('gmail');
  const { status, syncing, starting, syncNow } = useInboxSync();
  const disconnect = useDisconnectGmail();
  const [connecting, setConnecting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  // Say how the trip to Google went, once, then tidy the address bar.
  useEffect(() => {
    const result = outcome ? OUTCOMES[outcome] : null;
    if (!result) return;
    if (result.ok) toast.success(result.message);
    else toast.error(result.message);
    router.replace('/app/settings');
  }, [outcome, router]);

  async function connect() {
    setConnecting(true);
    try {
      window.location.href = await getGmailConnectUrl();
    } catch (error) {
      toast.error(errorMessage(error));
      setConnecting(false);
    }
  }

  const data = status.data;

  return (
    <SectionCard>
      <div className="flex flex-wrap items-center gap-4">
        <span className="bg-secondary text-muted-foreground flex size-10 shrink-0 items-center justify-center rounded-full">
          <Mail className="size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold">Gmail</h2>
          {status.isPending ? (
            <Skeleton className="mt-1.5 h-4 w-56" />
          ) : status.isError ? (
            <p className="text-destructive mt-0.5 text-sm">{errorMessage(status.error)}</p>
          ) : data?.connected ? (
            <p className="text-muted-foreground mt-0.5 text-sm">
              Connected to <span className="text-foreground font-medium">{data.account_email}</span>
              {syncing
                ? '. Reading your recent job mail…'
                : data.last_synced_at
                  ? `. Last read ${timeAgo(data.last_synced_at)}.`
                  : '.'}
            </p>
          ) : (
            <p className="text-muted-foreground mt-0.5 text-sm">
              Read-only access to job emails, so “application received”, interviews and rejections
              update your tracker for you.
            </p>
          )}
        </div>

        {status.isPending || status.isError ? null : data?.connected ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={syncing || starting}
              onClick={() => syncNow(undefined, { onError: (e) => toast.error(errorMessage(e)) })}
            >
              {syncing ? (
                <Loader2 className="animate-spin motion-reduce:animate-none" />
              ) : (
                <RefreshCw />
              )}
              {syncing ? 'Reading…' : 'Sync now'}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(true)}>
              Disconnect
            </Button>
          </div>
        ) : (
          <Button disabled={!data?.configured || connecting} onClick={() => void connect()}>
            {connecting ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : null}
            Connect Gmail
          </Button>
        )}
      </div>

      {data && !data.configured ? (
        <p className="bg-secondary mt-4 rounded-2xl px-4 py-3 text-sm">
          Gmail is not set up on this server yet. Add <code>GOOGLE_CLIENT_ID</code> and{' '}
          <code>GOOGLE_CLIENT_SECRET</code> to the backend settings and restart it.
        </p>
      ) : null}
      {data?.last_error ? (
        <div
          role="alert"
          className="bg-destructive/10 mt-4 flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3 text-sm"
        >
          <p className="min-w-0 flex-1">{data.last_error}</p>
          {/* Access was lost: the fix is to go through Google's consent screen again. */}
          <Button size="sm" disabled={connecting} onClick={() => void connect()}>
            Reconnect Gmail
          </Button>
        </div>
      ) : null}
      {data && !data.connected && data.configured ? (
        <p className="text-muted-foreground mt-4 text-xs leading-relaxed">
          We look only at job mail from the last {data.lookback_days} days and keep just the sender,
          subject, date and what kind of mail it was. The text of your mail is never stored, and
          nothing is ever sent from your account. Disconnecting deletes these records.
        </p>
      ) : null}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Disconnect Gmail?"
        description="We will stop reading your inbox and delete the mail records we kept. Your applications stay as they are."
        confirmLabel="Disconnect"
        pending={disconnect.isPending}
        onConfirm={() =>
          disconnect.mutate(undefined, {
            onSuccess: () => {
              setConfirming(false);
              toast.success('Gmail disconnected');
            },
            onError: (error) => toast.error(errorMessage(error)),
          })
        }
      />
    </SectionCard>
  );
}
