import { useMutation } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { ShareCard, ShareCreate } from '@/lib/api/types';
import { absoluteUrl } from '@/lib/site';

/** Makes a match's score card public. Asking again returns the same link. */
export async function shareMatch(matchId: string, body: ShareCreate): Promise<ShareCard> {
  const { data } = await api.post<ShareCard>(`/matches/${matchId}/share`, body);
  return data;
}

export async function stopSharing(slug: string): Promise<void> {
  await api.delete(`/shares/${slug}`);
}

export function shareUrl(slug: string): string {
  return absoluteUrl(`/s/${slug}`);
}

export function useShareMatch(matchId: string) {
  return useMutation({ mutationFn: (body: ShareCreate) => shareMatch(matchId, body) });
}

export function useStopSharing() {
  return useMutation({ mutationFn: stopSharing });
}
