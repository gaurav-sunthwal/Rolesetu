import { z } from 'zod';

import { firebaseAuth } from '@/lib/firebase';

const productionUrl = z.url().parse(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, '');
const localUrl = z
  .url()
  .parse(process.env.NEXT_PUBLIC_LOCAL_API_BASE_URL || 'http://localhost:8000')
  .replace(/\/$/, '');
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1']);

export type ApiTarget = { url: string; local: boolean };

let target: Promise<ApiTarget> | null = null;

async function pickTarget(): Promise<ApiTarget> {
  // Only a panel running on this computer looks for a backend on this computer.
  if (typeof window === 'undefined' || !LOCAL_HOSTS.has(window.location.hostname)) {
    return { url: productionUrl, local: false };
  }
  try {
    const response = await fetch(`${localUrl}/health`, { signal: AbortSignal.timeout(1500) });
    if (response.ok) return { url: localUrl, local: true };
  } catch {
    // No local backend running: use production.
  }
  return { url: productionUrl, local: false };
}

/**
 * Which API the panel talks to: the local backend when it is running and the
 * panel itself runs locally, else production. Decided once per page load, so
 * reload the page after starting or stopping the local backend.
 */
export function apiTarget(): Promise<ApiTarget> {
  target ??= pickTarget();
  return target;
}

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

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, string | undefined>;
  body?: unknown;
};

async function failure(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  const parsed = detailSchema.safeParse(body);
  const fallback =
    response.status === 403
      ? 'This account is not an admin.'
      : 'The server could not complete that. Please try again.';
  return new ApiError(parsed.success ? parsed.data.detail : fallback, response.status);
}

/** Sends one request as the signed-in admin and returns the successful response. */
async function request(path: string, options: RequestOptions): Promise<Response> {
  await firebaseAuth.authStateReady();
  const token = await firebaseAuth.currentUser?.getIdToken();
  const { url: baseUrl } = await apiTarget();
  const url = new URL(`${baseUrl}/api/v1${path}`);
  for (const [name, value] of Object.entries(options.params ?? {})) {
    if (value) url.searchParams.set(name, value);
  }

  // A file upload goes as it is; the browser sets its own Content-Type for it.
  const isForm = options.body instanceof FormData;
  const json = options.body !== undefined && !isForm;

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(json ? { 'Content-Type': 'application/json' } : {}),
      },
      body: isForm ? (options.body as FormData) : json ? JSON.stringify(options.body) : undefined,
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    throw new ApiError('Could not reach the server. Check your connection and try again.', null);
  }
  if (!response.ok) throw await failure(response);
  return response;
}

/**
 * Calls the Rolesetu API as the signed-in admin. The API decides whether the
 * account is an admin on every call; nothing here is trusted for that.
 */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await request(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json().catch(() => null)) as T;
}

/** Downloads a file (such as a resume PDF) as the signed-in admin. */
export async function apiFile(path: string): Promise<Blob> {
  const response = await request(path, {});
  return response.blob();
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Something unexpected went wrong. Try again.';
}
