import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  type ApplicationFilters,
  createApplication,
  deleteApplication,
  getApplication,
  getApplicationStats,
  listApplications,
  updateApplication,
} from '@/features/applications/api';
import type { ApplicationCreate, ApplicationUpdate } from '@/lib/api/types';

export const applicationKeys = {
  all: ['applications'] as const,
  list: (filters: ApplicationFilters) => ['applications', 'list', filters] as const,
  recent: (limit: number) => ['applications', 'recent', limit] as const,
  stats: ['applications', 'stats'] as const,
  detail: (id: string) => ['applications', 'detail', id] as const,
};

export function useApplications(filters: ApplicationFilters) {
  return useInfiniteQuery({
    queryKey: applicationKeys.list(filters),
    queryFn: ({ pageParam }) => listApplications(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    placeholderData: (previous) => previous,
  });
}

export function useRecentApplications(limit: number) {
  return useQuery({
    queryKey: applicationKeys.recent(limit),
    queryFn: () => listApplications({ status: null, search: '' }, null, limit),
  });
}

export function useApplicationStats() {
  return useQuery({ queryKey: applicationKeys.stats, queryFn: getApplicationStats });
}

export function useApplication(id: string | null) {
  return useQuery({
    queryKey: applicationKeys.detail(id ?? ''),
    queryFn: () => getApplication(id as string),
    enabled: id !== null,
  });
}

export function useCreateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ body, idempotencyKey }: { body: ApplicationCreate; idempotencyKey: string }) =>
      createApplication(body, idempotencyKey),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationKeys.all }),
  });
}

export function useUpdateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ApplicationUpdate }) =>
      updateApplication(id, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(applicationKeys.detail(updated.id), updated);
      return queryClient.invalidateQueries({ queryKey: applicationKeys.all });
    },
  });
}

export function useDeleteApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteApplication,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationKeys.all }),
  });
}
