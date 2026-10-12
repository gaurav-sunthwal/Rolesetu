import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef } from 'react';

import { applicationKeys } from '@/features/applications/hooks';
import {
  deleteInterview,
  disconnectGmail,
  getInboxStatus,
  type InterviewUpdate,
  listApplicationEmails,
  listInterviews,
  type InboxStatus,
  syncInbox,
  updateInterview,
} from '@/features/inbox/api';

export const inboxKeys = {
  all: ['inbox'] as const,
  status: ['inbox', 'status'] as const,
  interviews: ['inbox', 'interviews'] as const,
};

const POLL_WHILE_SYNCING_MS = 2500;

/** The connection and sync state. Polled while a sync is running, so the page updates itself. */
export function useInboxStatus() {
  return useQuery({
    queryKey: inboxKeys.status,
    queryFn: getInboxStatus,
    refetchInterval: (query) =>
      query.state.data?.sync_status === 'syncing' ? POLL_WHILE_SYNCING_MS : false,
  });
}

/** Everything a sync can change: the mails, the interviews and the tracker itself. */
export function useRefreshAfterSync() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['inbox', 'emails'] });
    void queryClient.invalidateQueries({ queryKey: inboxKeys.interviews });
    void queryClient.invalidateQueries({ queryKey: applicationKeys.all });
  }, [queryClient]);
}

export function useSyncInbox() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncInbox,
    onSuccess: (status) => queryClient.setQueryData<InboxStatus>(inboxKeys.status, status),
  });
}

export function useDisconnectGmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disconnectGmail,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inboxKeys.all }),
  });
}

export function useInterviews() {
  return useQuery({ queryKey: inboxKeys.interviews, queryFn: listInterviews });
}

export function useUpdateInterview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: InterviewUpdate }) => updateInterview(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inboxKeys.interviews }),
  });
}

export function useDeleteInterview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteInterview,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inboxKeys.interviews }),
  });
}

/** Mails linked to one application. Keyed under "emails" so a sync refreshes it too. */
export function useApplicationEmails(applicationId: string) {
  return useQuery({
    queryKey: ['inbox', 'emails', 'application', applicationId],
    queryFn: () => listApplicationEmails(applicationId),
  });
}

const STALE_AFTER_MS = 30 * 60 * 1000;

/**
 * Gmail syncing for a page: the current state, a way to start a sync, and two
 * things it does by itself. It refreshes what the page shows when a sync ends,
 * and it starts one whenever the last sync is 30 minutes old and the page is
 * open (there is no background worker yet, so an open page is what keeps the
 * tracker current).
 */
export function useInboxSync() {
  const status = useInboxStatus();
  const sync = useSyncInbox();
  const refresh = useRefreshAfterSync();
  const connected = status.data?.connected === true;
  const syncing = status.data?.sync_status === 'syncing';
  const lastSyncedAt = status.data?.last_synced_at;
  const start = sync.mutate;

  const wasSyncing = useRef(false);
  useEffect(() => {
    if (wasSyncing.current && !syncing) refresh();
    wasSyncing.current = syncing;
  }, [syncing, refresh]);

  // Checked on opening the page and then once a minute, so a page left open
  // keeps reading Gmail every 30 minutes without the user doing anything.
  useEffect(() => {
    if (!connected || !lastSyncedAt) return;
    const syncIfStale = () => {
      const stale = Date.now() - new Date(lastSyncedAt).getTime() >= STALE_AFTER_MS;
      if (stale && !syncing && !document.hidden) start();
    };
    syncIfStale();
    const timer = setInterval(syncIfStale, 60_000);
    return () => clearInterval(timer);
  }, [connected, syncing, lastSyncedAt, start]);

  return { status, connected, syncing, starting: sync.isPending, syncNow: sync.mutate };
}
