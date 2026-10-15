import { z } from 'zod';

import { firebaseAuth } from '@/lib/firebase';

const baseUrl = z.url().parse(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, '');

/** An API failure with a message that is safe to show. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const detailSchema = z.object({ detail: z.string() });

/**
 * Calls the Rolesetu API as the signed-in admin. The API decides whether the
 * account is an admin on every call; nothing here is trusted for that.
 */
export async function api<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'DELETE';
    params?: Record<string, string | undefined>;
    body?: unknown;
  } = {},
): Promise<T> {
  await firebaseAuth.authStateReady();
  const token = await firebaseAuth.currentUser?.getIdToken();
  const url = new URL(`${baseUrl}/api/v1${path}`);
  for (const [name, value] of Object.entries(options.params ?? {})) {
    if (value) url.searchParams.set(name, value);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    throw new ApiError('Could not reach the server. Check your connection and try again.', null);
  }
  if (response.status === 204) return undefined as T;

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = detailSchema.safeParse(body);
    const fallback =
      response.status === 403
        ? 'This account is not an admin.'
        : 'The server could not complete that. Please try again.';
    throw new ApiError(parsed.success ? parsed.data.detail : fallback, response.status);
  }
  return body as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Something unexpected went wrong. Try again.';
}
