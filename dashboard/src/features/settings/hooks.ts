import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { collectExport, deleteLlmKey, getLlmKeyStatus, saveLlmKey } from '@/features/settings/api';

const llmKey = ['llm-key'] as const;

export function useLlmKeyStatus() {
  return useQuery({ queryKey: llmKey, queryFn: getLlmKeyStatus });
}

export function useSaveLlmKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveLlmKey,
    onSuccess: (status) => queryClient.setQueryData(llmKey, status),
  });
}

export function useDeleteLlmKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteLlmKey,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: llmKey }),
  });
}

export function useExportData() {
  return useMutation({ mutationFn: collectExport });
}
