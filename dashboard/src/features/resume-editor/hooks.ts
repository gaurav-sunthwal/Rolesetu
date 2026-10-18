import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { profileKeys } from '@/features/profile/hooks';
import {
  type EditRequest,
  getResumeLayout,
  previewResumeEdits,
  saveResumeEdits,
} from '@/features/resume-editor/api';

export const editorKeys = {
  layout: ['resume-editor', 'layout'] as const,
  preview: (request: EditRequest | null) => ['resume-editor', 'preview', request] as const,
};

// Long enough to finish a word, short enough to feel live.
const PREVIEW_DELAY_MS = 500;

export function useResumeLayout() {
  return useQuery({
    queryKey: editorKeys.layout,
    queryFn: getResumeLayout,
    // "No resume yet" will not fix itself by asking again.
    retry: false,
    // Kept until the resume is replaced: refetching would not change it.
    staleTime: Infinity,
  });
}

function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

/**
 * The resume redrawn with the user's edits, a moment after they stop typing.
 * Each set of edits is asked for once; a newer one cancels the request in flight.
 */
export function useLivePreview(request: EditRequest | null) {
  const settled = useDebounced(request, PREVIEW_DELAY_MS);
  const query = useQuery({
    queryKey: editorKeys.preview(settled),
    queryFn: ({ signal }) => previewResumeEdits(settled as EditRequest, signal),
    enabled: settled !== null,
    // Keep showing the last preview while the next one is drawn.
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    gcTime: 60_000,
    retry: false,
  });
  return {
    ...query,
    // Still typing, or the latest edits are being drawn.
    isUpdating: request !== settled || query.isFetching,
    // The preview on screen belongs to the latest edits.
    isCurrent: request !== null && request === settled && !query.isPlaceholderData,
  };
}

/** Saves the edits as the resume. Everything that reads the resume or profile is refreshed. */
export function useSaveResumeEdits() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveResumeEdits,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['resume-editor'] });
      void queryClient.invalidateQueries({ queryKey: ['resume', 'latest'] });
      void queryClient.invalidateQueries({ queryKey: profileKeys.profile });
      void queryClient.invalidateQueries({ queryKey: ['tailoring', 'keywords'] });
    },
  });
}
