import { api } from '@/lib/api/client';
import type {
  ApplicationCreate,
  ApplicationDetail,
  ApplicationPage,
  ApplicationStats,
  ApplicationStatus,
  ApplicationUpdate,
} from '@/lib/api/types';

export type ApplicationFilters = { status: ApplicationStatus | null; search: string };

export async function listApplications(
  filters: ApplicationFilters,
  cursor: string | null,
  limit = 20,
): Promise<ApplicationPage> {
  const { data } = await api.get<ApplicationPage>('/applications', {
    params: {
      status: filters.status ?? undefined,
      q: filters.search || undefined,
      cursor: cursor ?? undefined,
      limit,
    },
  });
  return data;
}

export async function getApplicationStats(): Promise<ApplicationStats> {
  const { data } = await api.get<ApplicationStats>('/applications/stats');
  return data;
}

export async function getApplication(id: string): Promise<ApplicationDetail> {
  const { data } = await api.get<ApplicationDetail>(`/applications/${id}`);
  return data;
}

export async function createApplication(
  body: ApplicationCreate,
  idempotencyKey: string,
): Promise<ApplicationDetail> {
  const { data } = await api.post<ApplicationDetail>('/applications', body, {
    headers: { 'Idempotency-Key': idempotencyKey },
  });
  return data;
}

export async function updateApplication(
  id: string,
  body: ApplicationUpdate,
): Promise<ApplicationDetail> {
  const { data } = await api.patch<ApplicationDetail>(`/applications/${id}`, body);
  return data;
}

export async function deleteApplication(id: string): Promise<void> {
  await api.delete(`/applications/${id}`);
}
