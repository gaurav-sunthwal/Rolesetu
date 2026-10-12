import { listApplications } from '@/features/applications/api';
import { listMatches } from '@/features/matches/api';
import { getProfile, listSavedAnswers } from '@/features/profile/api';
import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import type { Application, LlmKeyStatus } from '@/lib/api/types';

export async function getLlmKeyStatus(): Promise<LlmKeyStatus> {
  const { data } = await api.get<LlmKeyStatus>('/llm-keys/me');
  return data;
}

export async function saveLlmKey(apiKey: string): Promise<LlmKeyStatus> {
  const { data } = await api.put<LlmKeyStatus>('/llm-keys/me', { api_key: apiKey });
  return data;
}

export async function deleteLlmKey(): Promise<void> {
  await api.delete('/llm-keys/me');
}

/** Everything the account holds, gathered for a download. */
export async function collectExport() {
  const applications: Application[] = [];
  let cursor: string | null = null;
  do {
    const page = await listApplications({ status: null, search: '' }, cursor, 50);
    applications.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);

  const [profile, savedAnswers, matches] = await Promise.all([
    getProfile(),
    listSavedAnswers(),
    listMatches(50),
  ]);

  return {
    exported_at: new Date().toISOString(),
    profile,
    saved_answers: savedAnswers,
    applications,
    recent_job_checks: matches.items,
  };
}

type ExtensionStatus = components['schemas']['ExtensionStatus'];
type ExtensionConnected = components['schemas']['ExtensionConnected'];

export async function getExtensionStatus(): Promise<ExtensionStatus> {
  const { data } = await api.get<ExtensionStatus>('/extension/status');
  return data;
}

/** Issues a fresh key for the browser extension. Any earlier key stops working. */
export async function connectExtension(): Promise<ExtensionConnected> {
  const { data } = await api.post<ExtensionConnected>('/extension/connect');
  return data;
}

export async function disconnectExtension(): Promise<void> {
  await api.delete('/extension/connection');
}
