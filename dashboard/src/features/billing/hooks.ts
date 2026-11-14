import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef, useState } from 'react';

import {
  cancelAutopay,
  createOrder,
  getPlan,
  startAutopay,
  track,
  verifyAutopay,
  verifyPayment,
} from '@/features/billing/api';
import { openCheckout } from '@/features/billing/checkout';
import { creditsKey } from '@/features/billing/credits';
import { errorMessage } from '@/lib/api/client';
import type { Plan } from '@/lib/api/types';

export const planKey = ['billing', 'plan'] as const;

export function usePlan() {
  return useQuery({ queryKey: planKey, queryFn: getPlan, staleTime: 60_000 });
}

/**
 * Where an upgrade is, so the screen can always say what is happening:
 * preparing (order on the server) → paying (Razorpay's window is open) →
 * confirming (server checks with Razorpay) → done. Or cancelled / failed.
 */
export type UpgradePhase =
  | { step: 'idle' }
  | { step: 'preparing' }
  | { step: 'paying' }
  | { step: 'confirming' }
  | { step: 'done'; plan: Plan }
  | { step: 'failed'; message: string; charged: boolean };

export type PayKind = 'autopay' | 'one_time';

function newAttemptId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`.replace(/[^0-9a-f-]/g, '0');
}

export function useUpgradeFlow() {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<UpgradePhase>({ step: 'idle' });
  const running = useRef(false);

  const start = useCallback(
    async (kind: PayKind = 'autopay') => {
      if (running.current) return; // a second click while one is going does nothing
      running.current = true;
      // One id for this attempt, from the click to its end, so the funnel can
      // follow it through the server and Razorpay's webhooks.
      const attempt = newAttemptId();
      track(kind === 'autopay' ? 'upgrade_clicked' : 'one_time_chosen', attempt, { kind });
      try {
        setPhase({ step: 'preparing' });
        const target =
          kind === 'autopay'
            ? ({ kind: 'autopay', subscription: await startAutopay(attempt) } as const)
            : ({ kind: 'order', order: await createOrder() } as const);

        setPhase({ step: 'paying' });
        track('checkout_opened', attempt, { kind });
        const result = await openCheckout(target, (failure) =>
          track('payment_failed', attempt, { kind, ...failure }),
        );
        if (result.kind === 'cancelled') {
          track('checkout_closed', attempt, { kind });
          setPhase({ step: 'idle' });
          return 'cancelled' as const;
        }
        if (result.kind === 'failed') {
          track('checkout_closed', attempt, { kind, after_failure: true });
          setPhase({ step: 'failed', message: result.message, charged: false });
          return 'failed' as const;
        }

        track('payment_succeeded', attempt, { kind });
        setPhase({ step: 'confirming' });
        try {
          const plan =
            result.payment.kind === 'autopay'
              ? await verifyAutopay(result.payment.proof)
              : await verifyPayment(result.payment.proof);
          queryClient.setQueryData(planKey, plan);
          setPhase({ step: 'done', plan });
          return 'done' as const;
        } catch (error) {
          // Razorpay took the payment but our check did not finish: the webhook will
          // still turn Pro on, so say that instead of "it failed".
          track('verify_failed', attempt, { kind, message: errorMessage(error) });
          setPhase({ step: 'failed', message: errorMessage(error), charged: true });
          return 'failed' as const;
        }
      } catch (error) {
        setPhase({ step: 'failed', message: errorMessage(error), charged: false });
        return 'failed' as const;
      } finally {
        running.current = false;
        void queryClient.invalidateQueries({ queryKey: planKey });
        // Pro raises this month's allowance at once.
        void queryClient.invalidateQueries({ queryKey: creditsKey });
      }
    },
    [queryClient],
  );

  const reset = useCallback(() => setPhase({ step: 'idle' }), []);

  return { phase, start, reset };
}

export function useCancelAutopay() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelAutopay,
    onSuccess: (plan) => queryClient.setQueryData(planKey, plan),
  });
}
