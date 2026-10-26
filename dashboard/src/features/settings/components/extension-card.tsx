'use client';

import { ExternalLink, Puzzle } from 'lucide-react';

import { SectionCard } from '@/components/app/section-card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { extensionStoreUrl } from '@/features/settings/extension-store';
import { useExtensionConnection } from '@/features/settings/extension-connection';
import { errorMessage } from '@/lib/api/client';
import { formatDate, timeAgo } from '@/lib/format';

export function ExtensionCard() {
  const {
    status,
    browser,
    connect,
    disconnect,
    loading,
    installed,
    connectedHere,
    connectedElsewhere,
    busy,
  } = useExtensionConnection();
  // Read only once the browser has answered, so the server never renders it.
  const storeUrl = browser.data ? extensionStoreUrl(navigator.userAgent) : null;

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
              yet. Install the Rolesetu extension, then press Reload to connect it.
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
            {installed ? (
              <Button onClick={() => connect.mutate({ automatic: false })} disabled={busy}>
                {connect.isPending ? 'Connecting…' : 'Connect extension'}
              </Button>
            ) : (
              <>
                {/* A page that was open before the install cannot see the extension. */}
                <Button variant="outline" onClick={() => window.location.reload()}>
                  Reload
                </Button>
                {storeUrl ? (
                  <Button
                    nativeButton={false}
                    render={<a href={storeUrl} target="_blank" rel="noreferrer" />}
                  >
                    Install extension
                    <ExternalLink data-icon="inline-end" />
                  </Button>
                ) : null}
              </>
            )}
          </div>
        )}
      </div>
    </SectionCard>
  );
}
