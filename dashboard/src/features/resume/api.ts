import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];
export type Resume = Schemas['ResumeRead'];
export type ResumeApplied = Schemas['ResumeApplied'];
export type ApplyMode = Schemas['ResumeApply']['mode'];
export type ResumeIdentity = Schemas['ResumeIdentity'];

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;

/** Checked before uploading, so an obvious mistake is caught without a round trip. */
export function fileProblem(file: File): string | null {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    return 'That is not a PDF. Export your resume as a PDF and upload that.';
  }
  if (file.size > MAX_RESUME_BYTES) return 'That file is larger than 5 MB. Export a smaller PDF.';
  if (file.size === 0) return 'That file is empty. Choose your resume PDF and try again.';
  return null;
}

/** The email and first name on a resume, read before sign-in. The file is not kept. */
export async function readResumeIdentity(file: File): Promise<ResumeIdentity> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<ResumeIdentity>('/public/resume-identity', form, {
    timeout: 60_000,
  });
  return data;
}

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
