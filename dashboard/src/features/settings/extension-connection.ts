'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { connectExtension, disconnectExtension, getExtensionStatus } from '@/features/settings/api';
import {
  clearExtensionKey,
  findExtension,
  giveKeyToExtension,
} from '@/features/settings/extension-bridge';
import { errorMessage } from '@/lib/api/client';

export const extensionStatusKey = ['extension', 'status'] as const;
export const extensionBrowserKey = ['extension', 'browser'] as const;

// Set when someone disconnects the extension in this browser, so it is not
// connected again behind their back. Connecting by hand clears it.
const optOutKey = 'rolesetu:extension-off';

export function hasOptedOut(): boolean {
  try {
    return window.localStorage.getItem(optOutKey) === '1';
  } catch {
    return false;
  }
}

function setOptedOut(value: boolean): void {
  try {
    if (value) window.localStorage.setItem(optOutKey, '1');
    else window.localStorage.removeItem(optOutKey);
  } catch {
    // Storage blocked: the extension may be connected again on its own, which is harmless.
  }
}

/** Connected without a click: no error toast, the header button stays as the way to retry. */
type ConnectOptions = { automatic: boolean };

/**
 * The extension's state in this browser and on the server, and the actions on
 * it. Used by the Settings card, the header button and the automatic connect,
 * so all of them change together.
 */
export function useExtensionConnection() {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: extensionStatusKey, queryFn: getExtensionStatus });
  // Asked of the browser, not the server: is the extension installed right here?
  const browser = useQuery({ queryKey: extensionBrowserKey, queryFn: findExtension, staleTime: 0 });

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: extensionStatusKey }),
      queryClient.invalidateQueries({ queryKey: extensionBrowserKey }),
    ]);

  const connect = useMutation<void, Error, ConnectOptions>({
    mutationFn: async () => {
      const { token } = await connectExtension();
      if (!(await giveKeyToExtension(token))) {
        // The key was issued but nothing received it: take it back.
        await disconnectExtension();
        throw new Error('not-installed');
      }
    },
    onSuccess: (_, { automatic }) => {
      setOptedOut(false);
      toast.success(
        automatic
          ? 'We connected the Rolesetu extension in this browser. Open a job page to see your score.'
          : 'Extension connected. Open a job page to see your score.',
      );
    },
    onError: (error, { automatic }) => {
      if (automatic) return;
      toast.error(
        error instanceof Error && error.message === 'not-installed'
          ? 'The extension did not respond. Check it is installed and enabled, then reload this page.'
          : errorMessage(error),
      );
    },
    onSettled: refresh,
  });

  const disconnect = useMutation({
    mutationFn: async () => {
      await disconnectExtension();
      await clearExtensionKey();
    },
    onSuccess: () => {
      setOptedOut(true);
      toast.success('Extension disconnected');
    },
    onError: (error) => toast.error(errorMessage(error)),
    onSettled: refresh,
  });

  const loading = status.isPending || browser.isPending;
  const installed = browser.data?.installed === true;
  // Connected only when the server has a key and this browser holds it.
  const connectedHere = status.data?.connected === true && browser.data?.connected === true;
  const connectedElsewhere = status.data?.connected === true && !connectedHere;

  return {
    status,
    browser,
    connect,
    disconnect,
    loading,
    installed,
    connectedHere,
    connectedElsewhere,
    busy: connect.isPending || disconnect.isPending,
  };
}
