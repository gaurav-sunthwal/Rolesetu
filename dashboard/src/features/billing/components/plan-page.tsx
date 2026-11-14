'use client';

import { Crown, ShieldCheck } from 'lucide-react';

import { PlanComparison } from '@/components/pricing/plan-comparison';
import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PRICE } from '@/content/pricing';
import { ReferralPanel } from '@/features/billing/components/referral-panel';
import { money, UpgradeButton } from '@/features/billing/components/upgrade-button';
import { CreditsMeter } from '@/features/billing/credits';
import { usePlan } from '@/features/billing/hooks';
import type { Plan } from '@/lib/api/types';
import { formatDate } from '@/lib/format';

export function PlanPage() {
  const plan = usePlan();

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Plan & invites</h1>
        <p className="text-muted-foreground max-w-2xl text-sm">
          Rolesetu is free to use. Pro adds far more AI for an active job hunt, and every friend you
          invite makes a month cheaper.
        </p>
      </header>

      {plan.isPending ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40 rounded-3xl" />
          <Skeleton className="h-40 rounded-3xl" />
        </div>
      ) : plan.isError ? (
        <SectionCard>
          <ErrorState error={plan.error} onRetry={() => void plan.refetch()} />
        </SectionCard>
      ) : (
        <PlanBody plan={plan.data} />
      )}
    </div>
  );
}

function PlanBody({ plan }: { plan: Plan }) {
  const isPro = plan.plan === 'pro';
  const price = money(plan.price.amount, plan.price.currency);
  const wasPrice = plan.referral_price ? `${PRICE.currency}${PRICE.pro}` : undefined;
  const canBuy = plan.payments_enabled && !plan.renew_from;

  const upgrade = plan.payments_enabled ? (
    <UpgradeButton
      size="lg"
      label={isPro ? `Add a month · ${price}` : `Upgrade to Pro · ${price}`}
      disabled={!canBuy}
    />
  ) : (
    <Button size="lg" disabled>
      Payments open soon
    </Button>
  );

  return (
    <>
      <div className="grid gap-4 md:grid-cols-[3fr_2fr]">
        <SectionCard>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-muted-foreground text-sm">Your plan</p>
              <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                {isPro ? <Crown className="text-primary size-6" aria-hidden /> : null}
                {isPro ? 'Pro' : 'Free'}
              </p>
              <p className="text-muted-foreground mt-1 text-sm">
                {isPro && plan.pro_until
                  ? `Active until ${formatDate(plan.pro_until)}. It does not renew by itself.`
                  : 'Free forever. Upgrade any time for more AI.'}
              </p>
            </div>
            <Badge variant={isPro ? 'default' : 'secondary'}>{isPro ? 'Pro' : 'Free'}</Badge>
          </div>
          <div className="mt-5">
            <CreditsMeter />
          </div>
        </SectionCard>

        <SectionCard className={plan.referral_price ? 'border-success/40 bg-success/5' : undefined}>
          <p className="text-muted-foreground text-sm">
            {isPro ? 'Your next month' : 'Pro costs you'}
          </p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-semibold">{price}</span>
            {wasPrice ? (
              <span className="text-muted-foreground line-through">{wasPrice}</span>
            ) : null}
            <span className="text-muted-foreground text-sm">/ month</span>
          </p>
          <p className="text-muted-foreground mt-1 text-sm">
            {plan.referral_price
              ? 'A friend you invited unlocked this price.'
              : `${PRICE.currency}${PRICE.referral} in any month you bring a friend.`}
          </p>
          <div className="mt-5 flex flex-col gap-2 [&>*]:w-full">{upgrade}</div>
          <p className="text-muted-foreground mt-3 flex items-center gap-1.5 text-xs">
            <ShieldCheck className="size-3.5" aria-hidden />
            {plan.renew_from
              ? `You can add the next month from ${formatDate(plan.renew_from)}.`
              : 'UPI, cards and net banking by Razorpay. No autopay.'}
          </p>
        </SectionCard>
      </div>

      <section aria-labelledby="compare-plans" className="flex flex-col gap-4">
        <h2 id="compare-plans" className="text-lg font-semibold">
          Free and Pro
        </h2>
        <PlanComparison
          currentPlan={isPro ? 'pro' : 'free'}
          proPrice={price}
          proWasPrice={wasPrice}
          freeAction={
            <Button variant="outline" size="lg" disabled>
              {isPro ? 'Included in Pro' : 'Your plan'}
            </Button>
          }
          proAction={upgrade}
        />
      </section>

      <ReferralPanel />

      {plan.payments.length > 0 ? (
        <SectionCard title="Payments">
          <ul className="divide-y rounded-2xl border text-sm">
            {plan.payments.map((payment) => (
              <li
                key={payment.paid_at}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
              >
                <span className="font-medium">{money(payment.amount, payment.currency)}</span>
                <span className="text-muted-foreground">
                  Paid {formatDate(payment.paid_at)} · Pro {formatDate(payment.pro_starts_at)} to{' '}
                  {formatDate(payment.pro_ends_at)}
                </span>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}
    </>
  );
}
