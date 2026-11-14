'use client';

import { ArrowRight, Crown, Gift } from 'lucide-react';
import Link from 'next/link';

import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PRICE } from '@/content/pricing';
import { money, UpgradeButton } from '@/features/billing/components/upgrade-button';
import { CreditsMeter } from '@/features/billing/credits';
import { usePlan } from '@/features/billing/hooks';
import { formatDate } from '@/lib/format';

/** The plan in short, for Settings. The full comparison and invites live on /app/plan. */
export function PlanCard() {
  const plan = usePlan();

  if (plan.isPending) return <Skeleton className="h-48 w-full rounded-3xl" />;
  if (plan.isError) {
    return (
      <SectionCard title="Plan">
        <ErrorState error={plan.error} onRetry={() => void plan.refetch()} className="py-6" />
      </SectionCard>
    );
  }

  const { data } = plan;
  const isPro = data.plan === 'pro';
  const price = money(data.price.amount, data.price.currency);

  return (
    <SectionCard
      title="Plan"
      description={
        isPro && data.pro_until
          ? data.autopay?.on
            ? `Pro renews automatically. Paid until ${formatDate(data.pro_until)}.`
            : `Pro until ${formatDate(data.pro_until)}. It does not renew by itself.`
          : `You're on Free. Pro is ${price} a month with autopay; cancel any time.`
      }
      action={
        <Badge variant={isPro ? 'default' : 'secondary'}>
          {isPro ? <Crown aria-hidden /> : null}
          {isPro ? 'Pro' : 'Free'}
        </Badge>
      }
    >
      <CreditsMeter />
      <div className="mt-5 flex flex-wrap items-center gap-3">
        {data.payments_enabled && !isPro ? <UpgradeButton /> : null}
        <Button variant="outline" nativeButton={false} render={<Link href="/app/plan" />}>
          Compare plans and invite friends
          <ArrowRight aria-hidden />
        </Button>
      </div>
      <p className="text-muted-foreground mt-3 flex items-center gap-1.5 text-xs">
        <Gift className="size-3.5" aria-hidden />
        {data.referral_price
          ? `A friend's invite unlocked your next month at ${price}.`
          : `Invite a friend and your next month is ${PRICE.currency}${PRICE.referral}.`}
      </p>
    </SectionCard>
  );
}
