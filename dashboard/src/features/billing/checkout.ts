import { z } from 'zod';

import type {
  CheckoutOrder,
  PaymentVerify,
  SubscriptionCheckout,
  SubscriptionVerify,
} from '@/lib/api/types';

const SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js';

/** What Razorpay's window hands back after a payment. Checked, never trusted:
 * the server verifies the signature and asks Razorpay before giving anything. */
const successSchema = z.object({
  razorpay_payment_id: z.string().min(1),
  razorpay_order_id: z.string().min(1),
  razorpay_signature: z.string().min(1),
});

interface RazorpayInstance {
  open(): void;
  on(event: 'payment.failed', listener: (response: unknown) => void): void;
}

type RazorpayConstructor = new (options: Record<string, unknown>) => RazorpayInstance;

let loading: Promise<RazorpayConstructor> | null = null;

function razorpayOnWindow(): RazorpayConstructor | null {
  const found: unknown = (window as unknown as { Razorpay?: unknown }).Razorpay;
  return typeof found === 'function' ? (found as RazorpayConstructor) : null;
}

/** Loads Razorpay's script the first time someone upgrades, not on every page. */
function loadRazorpay(): Promise<RazorpayConstructor> {
  const ready = razorpayOnWindow();
  if (ready) return Promise.resolve(ready);
  loading ??= new Promise<RazorpayConstructor>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => {
      const loaded = razorpayOnWindow();
      if (loaded) resolve(loaded);
      else reject(new Error('Razorpay did not load.'));
    };
    script.onerror = () => {
      script.remove();
      reject(new Error('Razorpay did not load.'));
    };
    document.head.appendChild(script);
  }).catch((error: unknown) => {
    loading = null; // let the next click try again
    throw error;
  });
  return loading;
}

/** Starts downloading Razorpay's script in the background, so the payment window
 * opens at once when the button is pressed. Safe to call often. */
export function preloadCheckout(): void {
  loadRazorpay().catch(() => undefined); // the click tries again and reports it
}

/** Razorpay's account of one failed try, kept for the payment funnel. Only codes
 * and words: Razorpay never sends card or account numbers here. */
export interface CheckoutFailure {
  code?: string;
  description?: string;
  reason?: string;
  source?: string;
  step?: string;
}

export type CheckoutResult =
  | { kind: 'paid'; payment: CheckoutProof }
  | { kind: 'cancelled' }
  | { kind: 'failed'; message: string };

/** The signed proof the window hands back: for an order, or for an autopay mandate. */
export type CheckoutProof =
  { kind: 'order'; proof: PaymentVerify } | { kind: 'autopay'; proof: SubscriptionVerify };

const subscriptionSuccessSchema = z.object({
  razorpay_payment_id: z.string().min(1),
  razorpay_subscription_id: z.string().min(1),
  razorpay_signature: z.string().min(1),
});

const failureDetailSchema = z.object({
  error: z.object({
    code: z.string().optional(),
    description: z.string().optional(),
    reason: z.string().optional(),
    source: z.string().optional(),
    step: z.string().optional(),
  }),
});

export type CheckoutTarget =
  { kind: 'order'; order: CheckoutOrder } | { kind: 'autopay'; subscription: SubscriptionCheckout };

/** Opens Razorpay's window for an order or an autopay mandate the server made, and
 * resolves once the person pays or closes it. A failed try is reported through
 * `onFailure` and the window stays open, so they can try another way to pay. */
export async function openCheckout(
  target: CheckoutTarget,
  onFailure: (failure: CheckoutFailure) => void = () => undefined,
): Promise<CheckoutResult> {
  let Razorpay: RazorpayConstructor;
  try {
    Razorpay = await loadRazorpay();
  } catch {
    return {
      kind: 'failed',
      message:
        'The payment window could not load. Check your connection, or turn off any blocker for checkout.razorpay.com, and try again.',
    };
  }

  return new Promise<CheckoutResult>((resolve) => {
    let settled = false;
    let lastFailure: string | undefined;
    const finish = (result: CheckoutResult) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };

    const common = {
      name: target.kind === 'order' ? target.order.name : target.subscription.name,
      description:
        target.kind === 'order' ? target.order.description : target.subscription.description,
      prefill: { email: target.kind === 'order' ? target.order.email : target.subscription.email },
      theme: { color: '#4f46e5' },
      modal: {
        ondismiss: () =>
          finish(
            lastFailure
              ? {
                  kind: 'failed',
                  message: `${lastFailure} Your payment did not go through and nothing was charged. Please try again or use another payment method.`,
                }
              : { kind: 'cancelled' },
          ),
      },
    };
    const notProven = {
      kind: 'failed' as const,
      message:
        'Razorpay did not send back a proof of payment. If you were charged, Pro turns on by itself within a few minutes.',
    };

    const checkout =
      target.kind === 'order'
        ? new Razorpay({
            ...common,
            key: target.order.key_id,
            order_id: target.order.order_id,
            amount: target.order.amount,
            currency: target.order.currency,
            handler: (response: unknown) => {
              const parsed = successSchema.safeParse(response);
              finish(
                parsed.success
                  ? { kind: 'paid', payment: { kind: 'order', proof: parsed.data } }
                  : notProven,
              );
            },
          })
        : new Razorpay({
            ...common,
            key: target.subscription.key_id,
            subscription_id: target.subscription.subscription_id,
            handler: (response: unknown) => {
              const parsed = subscriptionSuccessSchema.safeParse(response);
              finish(
                parsed.success
                  ? { kind: 'paid', payment: { kind: 'autopay', proof: parsed.data } }
                  : notProven,
              );
            },
          });

    checkout.on('payment.failed', (response) => {
      const parsed = failureDetailSchema.safeParse(response);
      const failure = parsed.success ? parsed.data.error : {};
      lastFailure = failure.description;
      onFailure(failure);
    });

    checkout.open();
  });
}
