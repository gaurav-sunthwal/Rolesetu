'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { toast } from 'sonner';

import { planKey } from '@/features/billing/hooks';
import { api, ApiError } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { useAuth } from '@/lib/auth-context';
import { SITE_URL } from '@/lib/site';

export type ReferralSummary = components['schemas']['ReferralSummary'];

export const referralsKey = ['billing', 'referrals'] as const;
const STORAGE_KEY = 'rolesetu.ref';
const CODE = /^[A-Za-z0-9]{6,12}$/;
// An invite remembered from a visit counts for a while, then is forgotten.
const KEEP_FOR_MS = 30 * 24 * 60 * 60 * 1000;

/** The invite link on the site the person is using (the live site in production,
 * a preview or localhost while testing), so the link always reaches this code. */
export function inviteLink(code: string): string {
  const origin = typeof window === 'undefined' ? SITE_URL : window.location.origin;
  return `${origin.replace(/\/$/, '')}/?ref=${encodeURIComponent(code)}`;
}

async function getReferrals(): Promise<ReferralSummary> {
  const { data } = await api.get<ReferralSummary>('/referrals/me');
  return data;
}

export function useReferrals() {
  return useQuery({ queryKey: referralsKey, queryFn: getReferrals });
}

function remembered(): string | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      'code' in parsed &&
      'at' in parsed &&
      typeof parsed.code === 'string' &&
      typeof parsed.at === 'number' &&
      CODE.test(parsed.code) &&
      Date.now() - parsed.at < KEEP_FOR_MS
    ) {
      return parsed.code;
    }
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked (private window): the invite is simply not remembered.
  }
  return null;
}

function forget() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing to clean up
  }
}

/** Remembers `?ref=CODE` from whatever page someone lands on, until they sign up. */
export function ReferralCapture() {
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get('ref');
    if (!code || !CODE.test(code)) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ code, at: Date.now() }));
    } catch {
      // Storage blocked: the invite is not remembered.
    }
  }, []);
  return null;
}

/** Once someone is signed in, records the invite they came through (once). */
export function ReferralClaimer() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const tried = useRef(false);
  const claim = useMutation({
    mutationFn: (code: string) => api.post('/referrals/claim', { code }),
  });

  useEffect(() => {
    if (!user || tried.current) return;
    const code = remembered();
    if (!code) return;
    tried.current = true;
    claim.mutate(code, {
      onSuccess: () => {
        forget();
        toast.success('You joined through a friend’s invite. Thanks for coming!');
        void queryClient.invalidateQueries({ queryKey: planKey });
      },
      onError: (error) => {
        // Refused for good (own link, already invited, old account): say why once and
        // stop trying. A network failure keeps it for the next visit.
        if (error instanceof ApiError && error.status !== null && error.status < 500) {
          forget();
          toast(`Invite not applied: ${error.message}`);
        }
      },
    });
  }, [user, claim, queryClient]);

  return null;
}
