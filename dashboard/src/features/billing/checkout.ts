import { z } from 'zod';

import type { CheckoutOrder, PaymentVerify } from '@/lib/api/types';

const SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js';

/** What Razorpay's window hands back after a payment. Checked, never trusted:
 * the server verifies the signature and asks Razorpay before giving anything. */
const successSchema = z.object({
  razorpay_payment_id: z.string().min(1),
  razorpay_order_id: z.string().min(1),
  razorpay_signature: z.string().min(1),
});

const failureSchema = z.object({
  error: z.object({ description: z.string().optional(), reason: z.string().optional() }),
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

export type CheckoutResult =
  | { kind: 'paid'; payment: PaymentVerify }
  | { kind: 'cancelled' }
  | { kind: 'failed'; message: string };

/** Opens Razorpay's payment window for an order the server made, and resolves
 * once the person pays, closes it, or the payment fails. */
export async function openCheckout(order: CheckoutOrder): Promise<CheckoutResult> {
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
    const finish = (result: CheckoutResult) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };

    const checkout = new Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount,
      currency: order.currency,
      name: order.name,
      description: order.description,
      prefill: { email: order.email },
      theme: { color: '#4f46e5' },
      handler: (response: unknown) => {
        const parsed = successSchema.safeParse(response);
        finish(
          parsed.success
            ? { kind: 'paid', payment: parsed.data }
            : {
                kind: 'failed',
                message:
                  'Razorpay did not send back a proof of payment. If you were charged, Pro turns on by itself within a few minutes.',
              },
        );
      },
      modal: {
        // Closing the window after a failed try also lands here, so a failure
        // reported first is kept.
        ondismiss: () => finish({ kind: 'cancelled' }),
      },
    });

    checkout.on('payment.failed', (response) => {
      const parsed = failureSchema.safeParse(response);
      const reason = parsed.success ? parsed.data.error.description : undefined;
      finish({
        kind: 'failed',
        message: `${reason ? `${reason} ` : ''}Your payment did not go through and nothing was charged. Please try again or use another payment method.`,
      });
    });

    checkout.open();
  });
}
