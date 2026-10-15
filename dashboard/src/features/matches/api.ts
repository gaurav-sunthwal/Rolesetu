import { api } from '@/lib/api/client';
import type { Match, MatchCreate, MatchPage } from '@/lib/api/types';

// With only a link the page is read first, and one that blocks us takes a slower second route.
const CREATE_TIMEOUT_MS = 60_000;

export async function createMatch(body: MatchCreate): Promise<Match> {
  const { data } = await api.post<Match>('/matches', body, { timeout: CREATE_TIMEOUT_MS });
  return data;
}

export async function getMatch(id: string): Promise<Match> {
  const { data } = await api.get<Match>(`/matches/${id}`);
  return data;
}

export async function listMatches(limit: number): Promise<MatchPage> {
  const { data } = await api.get<MatchPage>('/matches', { params: { limit } });
  return data;
}
