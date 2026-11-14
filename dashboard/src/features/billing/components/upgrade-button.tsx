'use client';

import { CheckCircle2, Circle, Crown, Loader2, ShieldCheck } from 'lucide-react';
import { type ComponentProps, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { preloadCheckout } from '@/features/billing/checkout';
import { type PayKind, type UpgradePhase, usePlan, useUpgradeFlow } from '@/features/billing/hooks';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

export function money(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: amount % 100 === 0 ? 0 : 2,
  }).format(amount / 100);
}

const STEPS = [
  { key: 'preparing', label: 'Opening secure checkout' },
  { key: 'paying', label: 'Pay with UPI, card or net banking' },
  { key: 'confirming', label: 'Confirming your payment with Razorpay' },
  { key: 'done', label: 'Pro is on' },
] as const;

function stepIndex(phase: UpgradePhase): number {
  const found = STEPS.findIndex((step) => step.key === phase.step);
  return found === -1 ? 0 : found;
}

/**
 * Upgrades on whatever page it is placed: Razorpay's window opens over the page
 * and, once paid, the person is back where they were, now on Pro. A small dialog
 * says what is happening before and after the payment window.
 */
export function UpgradeButton({
  label,
  className,
  oneTimeLink = false,
  ...buttonProps
}: {
  label?: string;
  /** Also offer paying for one month without autopay, for banks that can't do it. */
  oneTimeLink?: boolean;
} & Omit<ComponentProps<typeof Button>, 'onClick' | 'children'>) {
  const plan = usePlan(); // also opens the server's connection to Razorpay early
  const { phase, start, reset } = useUpgradeFlow();
  const [kind, setKind] = useState<PayKind>('autopay');

  // Fetch Razorpay's script while the person is still reading the page.
  useEffect(() => {
    const timer = window.setTimeout(preloadCheckout, 300);
    return () => window.clearTimeout(timer);
  }, []);

  const price = plan.data ? money(plan.data.price.amount, plan.data.price.currency) : null;
  const busy = phase.step === 'preparing' || phase.step === 'paying' || phase.step === 'confirming';
  // Hidden while Razorpay's own window is open: a dialog on top would trap the
  // keyboard and pointer away from it.
  const dialogOpen = phase.step !== 'idle' && phase.step !== 'paying';

  async function handleClick(chosen: PayKind = kind) {
    setKind(chosen);
    const outcome = await start(chosen);
    if (outcome === 'cancelled') toast('Payment cancelled. Nothing was charged.');
  }

  return (
    <>
      <Button
        {...buttonProps}
        className={className}
        onClick={() => void handleClick()}
        disabled={busy || buttonProps.disabled || plan.data?.payments_enabled === false}
      >
        {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Crown aria-hidden />}
        {label ?? (price ? `Start autopay · ${price}/month` : 'Upgrade to Pro')}
      </Button>
      {oneTimeLink ? (
        <button
          type="button"
          onClick={() => void handleClick('one_time')}
          disabled={busy || plan.data?.payments_enabled === false}
          className="text-muted-foreground hover:text-foreground self-start text-xs underline-offset-4 hover:underline disabled:opacity-50"
        >
          Bank doesn&rsquo;t support autopay? Pay for one month instead
        </button>
      ) : null}

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!open && !busy) reset(); // cannot be closed mid-payment by mistake
        }}
      >
        <DialogContent showCloseButton={!busy} aria-busy={busy}>
          <UpgradeStatus
            phase={phase}
            kind={kind}
            onRetry={() => void handleClick()}
            onClose={reset}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

function UpgradeStatus({
  phase,
  kind,
  onRetry,
  onClose,
}: {
  phase: UpgradePhase;
  kind: PayKind;
  onRetry: () => void;
  onClose: () => void;
}) {
  if (phase.step === 'failed') {
    return (
      <>
        <DialogHeader>
          <DialogTitle>
            {phase.charged ? 'Payment received, still confirming' : 'Payment did not go through'}
          </DialogTitle>
          <DialogDescription>{phase.message}</DialogDescription>
        </DialogHeader>
        {phase.charged ? (
          <p className="text-muted-foreground text-sm">
            Razorpay has your payment. Pro turns on by itself within a few minutes, and you will not
            be charged again. You can close this and keep working.
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          {phase.charged ? null : <Button onClick={onRetry}>Try again</Button>}
        </DialogFooter>
      </>
    );
  }

  const current = stepIndex(phase);
  const done = phase.step === 'done';
  return (
    <>
      <DialogHeader>
        <DialogTitle>{done ? "You're on Pro" : 'Upgrading to Pro'}</DialogTitle>
        <DialogDescription>
          {done && phase.plan.pro_until
            ? phase.plan.autopay?.on
              ? `Autopay is on: Pro renews every month until you cancel. Paid until ${formatDate(phase.plan.pro_until)}.`
              : `Pro is active until ${formatDate(phase.plan.pro_until)}. It does not renew by itself.`
            : 'Keep this page open. This takes a few seconds.'}
        </DialogDescription>
      </DialogHeader>

      <ol className="flex flex-col gap-3" aria-label="Upgrade progress">
        {STEPS.map((step, index) => {
          const complete = done || index < current;
          const active = !done && index === current;
          return (
            <li
              key={step.key}
              aria-current={active ? 'step' : undefined}
              className={cn(
                'flex items-center gap-3 text-sm',
                complete || active ? 'text-foreground' : 'text-muted-foreground',
              )}
            >
              {complete ? (
                <CheckCircle2 className="text-primary size-5 shrink-0" aria-hidden />
              ) : active ? (
                <Loader2 className="text-primary size-5 shrink-0 animate-spin" aria-hidden />
              ) : (
                <Circle className="size-5 shrink-0" aria-hidden />
              )}
              <span className={active ? 'font-medium' : undefined}>
                {step.key === 'paying' && kind === 'autopay'
                  ? 'Approve autopay in your UPI app or card'
                  : step.label}
              </span>
              <span className="sr-only">
                {complete ? '(done)' : active ? '(in progress)' : '(waiting)'}
              </span>
            </li>
          );
        })}
      </ol>

      {done ? (
        <DialogFooter>
          <Button onClick={onClose}>Continue</Button>
        </DialogFooter>
      ) : (
        <p className="text-muted-foreground flex items-center gap-2 text-xs">
          <ShieldCheck className="size-4" aria-hidden />
          Secured by Razorpay. Rolesetu never sees your card or UPI details.
        </p>
      )}
    </>
  );
}
