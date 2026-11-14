import { api } from '@/lib/api/client';
import type {
  CheckoutOrder,
  FunnelEventWrite,
  PaymentVerify,
  Plan,
  SubscriptionCheckout,
  SubscriptionVerify,
} from '@/lib/api/types';

export async function getPlan(): Promise<Plan> {
  const { data } = await api.get<Plan>('/billing/me');
  return data;
}

/** Starts a payment. Only the plan's name is sent: the server sets the price. */
export async function createOrder(): Promise<CheckoutOrder> {
  const { data } = await api.post<CheckoutOrder>('/billing/orders', { plan: 'pro_month' });
  return data;
}

export async function verifyPayment(payment: PaymentVerify): Promise<Plan> {
  // Razorpay is asked again on the server, which can take a few seconds.
  const { data } = await api.post<Plan>('/billing/orders/verify', payment, { timeout: 45_000 });
  return data;
}

/** Starts monthly autopay: the server makes the Razorpay subscription at its price. */
export async function startAutopay(attemptId: string): Promise<SubscriptionCheckout> {
  const { data } = await api.post<SubscriptionCheckout>('/billing/subscriptions', {
    attempt_id: attemptId,
  });
  return data;
}

export async function verifyAutopay(proof: SubscriptionVerify): Promise<Plan> {
  const { data } = await api.post<Plan>('/billing/subscriptions/verify', proof, {
    timeout: 45_000,
  });
  return data;
}

export async function cancelAutopay(): Promise<Plan> {
  const { data } = await api.post<Plan>('/billing/subscriptions/cancel');
  return data;
}

/** Tells the payment funnel about a step the browser saw. Never throws, never
 * waits: losing one event must not get in the way of paying. */
export function track(
  step: FunnelEventWrite['step'],
  attemptId?: string,
  detail: Record<string, string | number | boolean | undefined> = {},
): void {
  const clean = Object.fromEntries(
    Object.entries(detail).filter(
      (entry): entry is [string, string | number | boolean] => entry[1] !== undefined,
    ),
  );
  api
    .post('/billing/funnel', { step, attempt_id: attemptId ?? null, detail: clean })
    .catch(() => undefined);
}
