import { api } from '@/lib/api/client';
import type { CheckoutOrder, PaymentVerify, Plan } from '@/lib/api/types';

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
