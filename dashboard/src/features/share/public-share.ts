import { cacheLife } from 'next/cache';
import { z } from 'zod';

import type { ShareCard } from '@/lib/api/types';

const API = z.url().parse(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, '');

const cardSchema = z.object({
  slug: z.string(),
  role: z.string().nullable(),
  company: z.string().nullable(),
  score: z.number().int(),
  matched: z.array(z.string()),
  gaps: z.array(z.string()),
  created_at: z.string(),
}) satisfies z.ZodType<ShareCard>;

/**
 * A shared score card, read on the server for the public page and its preview
 * image. Cached for a few minutes, so a link taken down disappears soon after.
 * Null when the card was removed or never existed. Other failures throw, so
 * a brief outage is not remembered as "removed".
 */
async function fetchShare(slug: string): Promise<ShareCard | null> {
  'use cache';
  cacheLife({ stale: 60, revalidate: 300, expire: 3600 });
  const response = await fetch(`${API}/api/v1/public/shares/${slug}`, {
    signal: AbortSignal.timeout(8_000),
  });
  if (response.status === 404 || response.status === 422) return null;
  if (!response.ok) throw new Error(`Share lookup failed with ${response.status}`);
  const parsed = cardSchema.safeParse(await response.json());
  if (!parsed.success) throw new Error('Share lookup returned an unexpected shape');
  return parsed.data;
}

export type ShareLookup =
  { state: 'found'; card: ShareCard } | { state: 'missing' } | { state: 'unavailable' };

export async function getPublicShare(slug: string): Promise<ShareLookup> {
  if (!/^[A-Za-z0-9_-]{4,16}$/.test(slug)) return { state: 'missing' };
  try {
    const card = await fetchShare(slug);
    return card ? { state: 'found', card } : { state: 'missing' };
  } catch {
    return { state: 'unavailable' };
  }
}

export function jobLine(card: Pick<ShareCard, 'role' | 'company'>): string {
  if (card.role && card.company) return `${card.role} at ${card.company}`;
  return card.role ?? card.company ?? 'a job posting';
}
