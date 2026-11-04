import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { createMatch, getMatch, listMatches } from '@/features/matches/api';

// Most model-read jobs finish in a few seconds, so ask often.
const POLL_INTERVAL_MS = 1500;

export const matchKeys = {
  all: ['matches'] as const,
  recent: (limit: number) => ['matches', 'recent', limit] as const,
  detail: (id: string) => ['matches', 'detail', id] as const,
};

export function useCreateMatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMatch,
    onSuccess: (match) => {
      queryClient.setQueryData(matchKeys.detail(match.id), match);
      return queryClient.invalidateQueries({ queryKey: matchKeys.all, refetchType: 'none' });
    },
  });
}

/** Scoring runs in the background, so this keeps asking until it is done. */
export function useMatch(id: string | null) {
  return useQuery({
    queryKey: matchKeys.detail(id ?? ''),
    queryFn: () => getMatch(id as string),
    enabled: id !== null,
    // A finished check never changes, and the one just created may not be saved
    // yet (the server answers first, then saves): it is not asked for again.
    staleTime: (query) => (query.state.data?.status === 'completed' ? Infinity : 0),
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? POLL_INTERVAL_MS : false),
  });
}

export function useRecentMatches(limit: number) {
  return useQuery({ queryKey: matchKeys.recent(limit), queryFn: () => listMatches(limit) });
}
