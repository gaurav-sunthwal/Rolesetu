import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { profileKeys } from '@/features/profile/hooks';
import {
  createTailoredResume,
  getKeywordCheck,
  keepTailoredResume,
} from '@/features/tailoring/api';

/** The job's title and skills compared with the words on the user's resume. */
export function useKeywordCheck(matchId: string) {
  return useQuery({
    queryKey: ['tailoring', 'keywords', matchId],
    queryFn: () => getKeywordCheck(matchId),
    // "No resume yet" will not fix itself by asking again.
    retry: false,
  });
}

/** Builds a preview. Nothing is saved and the profile does not change. */
export function useTailorResume() {
  return useMutation({ mutationFn: createTailoredResume });
}

/**
 * Makes the previewed copy the saved resume. The resume, the profile and the
 * keyword checks all change together, so everything that shows them is refreshed.
 */
export function useKeepTailoredResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: keepTailoredResume,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: profileKeys.profile });
      void queryClient.invalidateQueries({ queryKey: ['resume', 'latest'] });
      void queryClient.invalidateQueries({ queryKey: ['tailoring', 'keywords'] });
    },
  });
}
