'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Puzzle } from 'lucide-react';
import { toast } from 'sonner';

import { SectionCard } from '@/components/app/section-card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { connectExtension, disconnectExtension, getExtensionStatus } from '@/features/settings/api';
import {
  clearExtensionKey,
  findExtension,
  giveKeyToExtension,
} from '@/features/settings/extension-bridge';
import { errorMessage } from '@/lib/api/client';
import { formatDate, timeAgo } from '@/lib/format';

const statusKey = ['extension', 'status'] as const;
const browserKey = ['extension', 'browser'] as const;

export function ExtensionCard() {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: statusKey, queryFn: getExtensionStatus });
  // Asked of the browser, not the server: is the extension installed right here?
  const browser = useQuery({ queryKey: browserKey, queryFn: findExtension, staleTime: 0 });

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: statusKey }),
      queryClient.invalidateQueries({ queryKey: browserKey }),
    ]);

  const connect = useMutation({
    mutationFn: async () => {
      const { token } = await connectExtension();
      if (!(await giveKeyToExtension(token))) {
        // The key was issued but nothing received it: take it back.
        await disconnectExtension();
        throw new Error('not-installed');
      }
    },
    onSuccess: () => toast.success('Extension connected. Open a job page to see your score.'),
    onError: (error) =>
      toast.error(
        error instanceof Error && error.message === 'not-installed'
          ? 'The extension did not respond. Check it is installed and enabled, then reload this page.'
          : errorMessage(error),
      ),
    onSettled: refresh,
  });

  const disconnect = useMutation({
    mutationFn: async () => {
      await disconnectExtension();
      await clearExtensionKey();
    },
    onSuccess: () => toast.success('Extension disconnected'),
    onError: (error) => toast.error(errorMessage(error)),
    onSettled: refresh,
  });

  const loading = status.isPending || browser.isPending;
  const installed = browser.data?.installed === true;
  // Connected only when the server has a key and this browser holds it.
  const connectedHere = status.data?.connected === true && browser.data?.connected === true;
  const connectedElsewhere = status.data?.connected === true && !connectedHere;
  const busy = connect.isPending || disconnect.isPending;

  return (
    <SectionCard>
      <div className="flex flex-wrap items-start gap-4">
        <span className="bg-secondary text-muted-foreground flex size-10 shrink-0 items-center justify-center rounded-full">
          <Puzzle className="size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold">Browser extension</h2>
          {loading ? (
            <Skeleton className="mt-2 h-4 w-64" />
          ) : status.isError ? (
            <p className="text-destructive mt-0.5 text-sm">{errorMessage(status.error)}</p>
          ) : connectedHere ? (
            <p className="text-muted-foreground mt-0.5 text-sm">
              Connected
              {status.data?.connected_at ? ` on ${formatDate(status.data.connected_at)}` : ''}.{' '}
              {status.data?.last_used_at
                ? `Last used ${timeAgo(status.data.last_used_at)}.`
                : 'Not used yet.'}{' '}
              Your match score now appears on job pages.
            </p>
          ) : !installed ? (
            <p className="text-muted-foreground mt-0.5 text-sm">
              Shows your match score on job pages as you browse. It is not installed in this browser
              yet. Install it, then reload this page to connect it.
            </p>
          ) : connectedElsewhere ? (
            <p className="text-muted-foreground mt-0.5 text-sm">
              Your account is connected to the extension in another browser. Connecting here moves
              it to this one.
            </p>
          ) : (
            <p className="text-muted-foreground mt-0.5 text-sm">
              The extension is installed. Connect it to your account so it can show your match score
              on job pages.
            </p>
          )}
        </div>
        {loading || status.isError ? null : connectedHere ? (
          <Button variant="outline" onClick={() => disconnect.mutate()} disabled={busy}>
            {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
          </Button>
        ) : (
          <div className="flex flex-wrap gap-2">
            {connectedElsewhere ? (
              <Button variant="ghost" onClick={() => disconnect.mutate()} disabled={busy}>
                Disconnect
              </Button>
            ) : null}
            <Button onClick={() => connect.mutate()} disabled={busy || !installed}>
              {connect.isPending ? 'Connecting…' : 'Connect extension'}
            </Button>
          </div>
        )}
      </div>
    </SectionCard>
  );
}
