import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { profileKeys } from '@/features/profile/hooks';
import {
  type ApplyMode,
  applyResume,
  deleteResume,
  getLatestResume,
  type Resume,
  uploadResume,
} from '@/features/resume/api';

const latestKey = ['resume', 'latest'] as const;

export function useLatestResume() {
  return useQuery({ queryKey: latestKey, queryFn: getLatestResume });
}

export function useUploadResume() {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState(0);
  const mutation = useMutation({
    mutationFn: (file: File) => {
      setProgress(0);
      return uploadResume(file, setProgress);
    },
    onSuccess: (resume) => queryClient.setQueryData<Resume | null>(latestKey, resume),
  });
  return { ...mutation, progress };
}

export function useApplyResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: ApplyMode }) => applyResume(id, mode),
    onSuccess: ({ resume, profile }) => {
      queryClient.setQueryData<Resume | null>(latestKey, resume);
      queryClient.setQueryData(profileKeys.profile, profile);
    },
  });
}

export function useDeleteResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteResume,
    onSuccess: () => queryClient.setQueryData<Resume | null>(latestKey, null),
  });
}
