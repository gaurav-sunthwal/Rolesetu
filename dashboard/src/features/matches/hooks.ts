import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { createMatch, getMatch, listMatches } from '@/features/matches/api';

const POLL_INTERVAL_MS = 2500;

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
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? POLL_INTERVAL_MS : false),
  });
}

export function useRecentMatches(limit: number) {
  return useQuery({ queryKey: matchKeys.recent(limit), queryFn: () => listMatches(limit) });
}
