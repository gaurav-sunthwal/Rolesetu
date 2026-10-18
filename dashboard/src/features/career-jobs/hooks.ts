import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addCareerCompany,
  type CareerJobFilters,
  listCareerCompanies,
  listCareerJobs,
} from '@/features/career-jobs/api';

export const careerJobKeys = {
  all: ['career-jobs'] as const,
  companies: ['career-jobs', 'companies'] as const,
  list: (filters: CareerJobFilters) => ['career-jobs', 'list', filters] as const,
};

export function useCareerCompanies() {
  return useQuery({ queryKey: careerJobKeys.companies, queryFn: listCareerCompanies });
}

export function useCareerJobs(filters: CareerJobFilters, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: careerJobKeys.list(filters),
    queryFn: ({ pageParam }) => listCareerJobs(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    placeholderData: (previous) => previous,
    enabled,
  });
}

export function useAddCareerCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: addCareerCompany,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: careerJobKeys.all }),
  });
}
