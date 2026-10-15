import { api } from '@/lib/api/client';
import type { JobPreview } from '@/lib/api/types';

// Reading a page that blocks us goes through a slower second route.
const PREVIEW_TIMEOUT_MS = 60_000;

/** What a job asks for, read from its link. Works without signing in. */
export async function previewJob(url: string): Promise<JobPreview> {
  const { data } = await api.post<JobPreview>(
    '/public/job-previews',
    { url },
    { timeout: PREVIEW_TIMEOUT_MS },
  );
  return data;
}
