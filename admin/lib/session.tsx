'use client';

import { useQuery } from '@tanstack/react-query';
import { onAuthStateChanged, type User } from 'firebase/auth';
import { useEffect, useState } from 'react';

import { api } from '@/lib/api';
import { firebaseAuth } from '@/lib/firebase';
import type { Admin } from '@/lib/types';

/** The Google account signed in to this tab, or null. `undefined` while Firebase is starting. */
export function useGoogleAccount(): User | null | undefined {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  useEffect(() => onAuthStateChanged(firebaseAuth, setUser), []);
  return user;
}

/** Asks the API whether the signed-in account is an admin. */
export function useAdmin(uid: string | null) {
  return useQuery({
    queryKey: ['admin', 'me', uid],
    queryFn: () => api<Admin>('/admin/me'),
    enabled: uid !== null,
    retry: false,
    staleTime: 60_000,
  });
}
