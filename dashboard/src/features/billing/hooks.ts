import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef, useState } from 'react';

import { createOrder, getPlan, verifyPayment } from '@/features/billing/api';
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

export function useUpgradeFlow() {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<UpgradePhase>({ step: 'idle' });
  const running = useRef(false);

  const start = useCallback(async () => {
    if (running.current) return; // a second click while one is going does nothing
    running.current = true;
    try {
      setPhase({ step: 'preparing' });
      const order = await createOrder();

      setPhase({ step: 'paying' });
      const result = await openCheckout(order);
      if (result.kind === 'cancelled') {
        setPhase({ step: 'idle' });
        return 'cancelled' as const;
      }
      if (result.kind === 'failed') {
        setPhase({ step: 'failed', message: result.message, charged: false });
        return 'failed' as const;
      }

      setPhase({ step: 'confirming' });
      try {
        const plan = await verifyPayment(result.payment);
        queryClient.setQueryData(planKey, plan);
        setPhase({ step: 'done', plan });
        return 'done' as const;
      } catch (error) {
        // Razorpay took the money but our check did not finish: the webhook will
        // still turn Pro on, so say that instead of "it failed".
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
  }, [queryClient]);

  const reset = useCallback(() => setPhase({ step: 'idle' }), []);

  return { phase, start, reset };
}
