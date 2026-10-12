'use client';

import { Loader2, Mail, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { useInboxSync } from '@/features/inbox/hooks';
import { errorMessage } from '@/lib/api/client';
import { timeAgo } from '@/lib/format';

/**
 * Reads the user's Gmail now and updates the tracker. Shown where the
 * applications are, so nobody has to go looking for it. Before Gmail is
 * connected, it offers to connect instead.
 */
export function SyncButton() {
  const { status, connected, syncing, starting, syncNow } = useInboxSync();
  const data = status.data;
  if (!data?.configured) return null;

  if (!connected) {
    return (
      <Button variant="outline" nativeButton={false} render={<Link href="/app/settings" />}>
        <Mail />
        Connect Gmail
      </Button>
    );
  }

  const busy = syncing || starting;
  return (
    <Button
      variant="outline"
      disabled={busy}
      title={
        data.last_error ??
        (data.last_synced_at ? `Gmail last read ${timeAgo(data.last_synced_at)}` : undefined)
      }
      onClick={() =>
        syncNow(undefined, {
          onSuccess: () => toast.success('Reading your Gmail. New mail will show up here shortly.'),
          onError: (error) => toast.error(errorMessage(error)),
        })
      }
    >
      {busy ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}
      {busy ? 'Reading Gmail…' : 'Sync now'}
    </Button>
  );
}

/**
 * One line saying how fresh the Gmail data is and how to get it sooner. Shown
 * only when Gmail is connected.
 */
export function SyncNote() {
  const { status, connected, syncing } = useInboxSync();
  const data = status.data;
  if (!data || !connected) return null;

  if (data.last_error) {
    return (
      <p role="alert" className="text-destructive text-sm">
        {data.last_error}
      </p>
    );
  }
  return (
    <p className="text-muted-foreground text-sm">
      {syncing
        ? 'Reading your Gmail now…'
        : `While Rolesetu is open, your Gmail is checked every 30 minutes${
            data.last_synced_at ? ` (last checked ${timeAgo(data.last_synced_at)})` : ''
          }. Want the latest right away? Press “Sync now”.`}
    </p>
  );
}
