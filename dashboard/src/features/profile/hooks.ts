import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  deleteSavedAnswer,
  getProfile,
  listSavedAnswers,
  saveProfile,
  setSavedAnswer,
} from '@/features/profile/api';
import type { Profile, ProfileWrite } from '@/lib/api/types';

export const profileKeys = {
  profile: ['profile'] as const,
  savedAnswers: ['saved-answers'] as const,
};

export function useProfile() {
  return useQuery({ queryKey: profileKeys.profile, queryFn: getProfile });
}

export function toWrite(profile: Profile): ProfileWrite {
  return {
    full_name: profile.full_name,
    headline: profile.headline,
    location: profile.location,
    phone: profile.phone,
    links: profile.links,
    skills: profile.skills,
    experience: profile.experience,
    projects: profile.projects,
    education: profile.education,
  };
}

/**
 * Saves one change to the profile.
 *
 * The API replaces the whole profile on each save, so two saves in flight at
 * once could land out of order and the older one would win. To prevent that:
 * - the cache always holds every edit made so far (applied in `onMutate`);
 * - saves run one at a time (`scope`), each sending the cache as it is then;
 * - a reply only updates the server-computed fields, never the lists, so it
 *   cannot wipe out an edit that is still waiting its turn.
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    scope: { id: 'profile' },
    mutationFn: () => {
      const latest = queryClient.getQueryData<Profile>(profileKeys.profile);
      if (!latest) throw new Error('Profile is not loaded yet');
      return saveProfile(toWrite(latest));
    },
    onMutate: async (change: (current: ProfileWrite) => ProfileWrite) => {
      await queryClient.cancelQueries({ queryKey: profileKeys.profile });
      queryClient.setQueryData<Profile>(profileKeys.profile, (current) =>
        current ? { ...current, ...change(toWrite(current)) } : current,
      );
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<Profile>(profileKeys.profile, (current) =>
        current
          ? {
              ...current,
              version: saved.version,
              completeness: saved.completeness,
              updated_at: saved.updated_at,
            }
          : saved,
      );
    },
    // The edit was not saved: drop what we showed and reload what the server has.
    onError: () => queryClient.invalidateQueries({ queryKey: profileKeys.profile }),
  });
}

export function useSavedAnswers() {
  return useQuery({ queryKey: profileKeys.savedAnswers, queryFn: listSavedAnswers });
}

export function useSetSavedAnswer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, answer }: { key: string; answer: string }) => setSavedAnswer(key, answer),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: profileKeys.savedAnswers }),
  });
}

export function useDeleteSavedAnswer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSavedAnswer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: profileKeys.savedAnswers }),
  });
}
