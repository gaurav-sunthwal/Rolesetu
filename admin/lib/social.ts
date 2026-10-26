import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type {
  ConnectUrl,
  ImageUploaded,
  SocialOverview,
  SocialPlatform,
  SocialPost,
  SocialPostPage,
  SocialPostWrite,
  SocialProvider,
} from '@/lib/types';

const KEY = ['admin', 'social'] as const;

export const PLATFORM_NAMES: Record<SocialPlatform, string> = {
  linkedin: 'LinkedIn',
  facebook: 'Facebook',
  instagram: 'Instagram',
};

// The same limits the API checks, so the counter can warn while typing.
export const TEXT_LIMITS: Record<SocialPlatform, number> = {
  linkedin: 3000,
  facebook: 60000,
  instagram: 2200,
};

export function useSocialOverview() {
  return useQuery({
    queryKey: [...KEY, 'overview'],
    queryFn: () => api<SocialOverview>('/admin/social'),
  });
}

export function useSocialPosts() {
  return useInfiniteQuery({
    queryKey: [...KEY, 'posts'],
    queryFn: ({ pageParam }) =>
      api<SocialPostPage>('/admin/social/posts', { params: { cursor: pageParam } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    // Scheduled posts change on the server as they go out; keep the list current.
    refetchInterval: (query) => {
      const posts = query.state.data?.pages.flatMap((page) => page.items) ?? [];
      return posts.some((post) => post.status === 'scheduled' || post.status === 'publishing')
        ? 30_000
        : false;
    },
  });
}

/** Sends the browser to the platform's consent screen. It comes back to /social. */
export async function startConnecting(provider: SocialProvider): Promise<void> {
  const { url } = await api<ConnectUrl>(`/admin/social/${provider}/connect-url`);
  window.location.assign(url);
}

export async function uploadImage(file: File): Promise<string> {
  const form = new FormData();
  form.append('file', file);
  const { url } = await api<ImageUploaded>('/admin/social/images', { method: 'POST', body: form });
  return url;
}

function useSocialMutation<T>(fn: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDisconnect() {
  return useSocialMutation((accountId: string) =>
    api<void>(`/admin/social/accounts/${accountId}`, { method: 'DELETE' }),
  );
}

export function useSavePost() {
  return useSocialMutation(({ id, body }: { id: string | null; body: SocialPostWrite }) =>
    id
      ? api<SocialPost>(`/admin/social/posts/${id}`, { method: 'PUT', body })
      : api<SocialPost>('/admin/social/posts', { method: 'POST', body }),
  );
}

export function useSchedulePost() {
  return useSocialMutation(({ id, at }: { id: string; at: string | null }) =>
    api<SocialPost>(`/admin/social/posts/${id}/schedule`, { method: 'POST', body: { at } }),
  );
}

export function usePostAction() {
  return useSocialMutation(({ id, action }: { id: string; action: 'unschedule' | 'retry' }) =>
    api<SocialPost>(`/admin/social/posts/${id}/${action}`, { method: 'POST' }),
  );
}

export function useDeletePost() {
  return useSocialMutation((id: string) =>
    api<void>(`/admin/social/posts/${id}`, { method: 'DELETE' }),
  );
}
