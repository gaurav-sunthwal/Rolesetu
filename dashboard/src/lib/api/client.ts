import axios, { AxiosError } from 'axios';
import { z } from 'zod';

import { firebaseAuth } from '@/lib/firebase';

const baseURL = z.url().parse(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, '');

export const api = axios.create({ baseURL: `${baseURL}/api/v1`, timeout: 20_000 });

api.interceptors.request.use(async (config) => {
  // Resolves immediately once Firebase has restored the session.
  await firebaseAuth.authStateReady();
  const token = await firebaseAuth.currentUser?.getIdToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** An API failure with a message that is safe to show to the user. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const detailSchema = z.object({
  detail: z.union([z.string(), z.array(z.object({ msg: z.string() }))]),
});

function messageFor(error: AxiosError): string {
  if (!error.response) {
    return error.code === 'ECONNABORTED'
      ? 'The server took too long to respond. Please try again.'
      : 'Could not reach the server. Check your connection and try again.';
  }
  const parsed = detailSchema.safeParse(error.response.data);
  if (parsed.success) {
    const { detail } = parsed.data;
    if (typeof detail === 'string') return detail;
    if (detail[0]) return detail[0].msg.replace(/^Value error, /, '');
  }
  if (error.response.status === 401) return 'Your session has expired. Please sign in again.';
  if (error.response.status >= 500) return 'The server ran into a problem. Please try again.';
  return 'That request could not be completed. Please try again.';
}

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (error instanceof AxiosError) {
      throw new ApiError(messageFor(error), error.response?.status ?? null);
    }
    throw error;
  },
);

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Something unexpected happened. Try again.';
}
