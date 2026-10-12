import { api } from '@/lib/api/client';
import type { Profile, ProfileWrite, SavedAnswer } from '@/lib/api/types';

export async function getProfile(): Promise<Profile> {
  const { data } = await api.get<Profile>('/profile/me');
  return data;
}

export async function saveProfile(body: ProfileWrite): Promise<Profile> {
  const { data } = await api.put<Profile>('/profile/me', body);
  return data;
}

export async function listSavedAnswers(): Promise<SavedAnswer[]> {
  const { data } = await api.get<SavedAnswer[]>('/saved-answers');
  return data;
}

export async function setSavedAnswer(key: string, answer: string): Promise<SavedAnswer> {
  const { data } = await api.put<SavedAnswer>(`/saved-answers/${key}`, { answer });
  return data;
}

export async function deleteSavedAnswer(key: string): Promise<void> {
  await api.delete(`/saved-answers/${key}`);
}
