import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];
export type Resume = Schemas['ResumeRead'];
export type ResumeApplied = Schemas['ResumeApplied'];
export type ApplyMode = Schemas['ResumeApply']['mode'];

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;

export async function getLatestResume(): Promise<Resume | null> {
  const { data } = await api.get<Resume | null>('/resume/latest');
  return data;
}

export async function uploadResume(
  file: File,
  onProgress: (fraction: number) => void,
): Promise<Resume> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<Resume>('/resume', form, {
    // Uploads on a slow connection need longer than an ordinary request.
    timeout: 90_000,
    onUploadProgress: (event) => {
      if (event.total) onProgress(event.loaded / event.total);
    },
  });
  return data;
}

export async function applyResume(id: string, mode: ApplyMode): Promise<ResumeApplied> {
  const { data } = await api.post<ResumeApplied>(`/resume/${id}/apply`, { mode });
  return data;
}

export async function getResumeDownloadLink(id: string): Promise<string> {
  const { data } = await api.get<Schemas['DownloadLink']>(`/resume/${id}/download-link`);
  return data.url;
}

export async function deleteResume(id: string): Promise<void> {
  await api.delete(`/resume/${id}`);
}
