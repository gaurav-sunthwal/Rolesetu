import { api } from '@/lib/api/client';
import type { Match, MatchCreate, MatchPage } from '@/lib/api/types';

export async function createMatch(body: MatchCreate): Promise<Match> {
  const { data } = await api.post<Match>('/matches', body);
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
