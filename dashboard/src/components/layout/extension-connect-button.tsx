'use client';

import { Puzzle } from 'lucide-react';
import { useEffect, useRef } from 'react';

import { Button } from '@/components/ui/button';
import { hasOptedOut, useExtensionConnection } from '@/features/settings/extension-connection';

/**
 * Connects the extension in this browser without a click when it is installed
 * and the account is not connected anywhere yet. Otherwise, while it is
 * installed but not connected here, offers a button to do it.
 *
 * It never connects on its own when the account uses the extension in another
 * browser (connecting moves the key, which would switch that one off), or when
 * the user disconnected it here themselves.
 */
export function ExtensionConnectButton() {
  const { status, loading, installed, connectedHere, connect, busy } = useExtensionConnection();
  const tried = useRef(false);

  const canAutoConnect =
    !loading && installed && status.data?.connected === false && !hasOptedOut();

  useEffect(() => {
    if (!canAutoConnect || tried.current) return;
    tried.current = true;
    connect.mutate({ automatic: true });
  }, [canAutoConnect, connect]);

  if (loading || status.isError || !installed || connectedHere) return null;

  return (
    <Button
      variant="outline"
      onClick={() => connect.mutate({ automatic: false })}
      disabled={busy}
      aria-label="Connect extension"
    >
      <Puzzle />
      <span className="hidden sm:inline">
        {connect.isPending ? 'Connecting…' : 'Connect extension'}
      </span>
    </Button>
  );
}
