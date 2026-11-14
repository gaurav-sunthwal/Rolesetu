'use client';

import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { PRICE } from '@/content/pricing';
import { useAuth } from '@/lib/auth-context';

/** A plan's button on the landing page: sign up, or straight to the Plan page. */
export function PricingAction({ plan }: { plan: 'free' | 'pro' }) {
  const { user } = useAuth();

  if (plan === 'free') {
    return (
      <Button
        variant="outline"
        size="lg"
        nativeButton={false}
        render={<Link href={user ? '/app' : '/login'} />}
      >
        {user ? 'Open dashboard' : 'Start free'}
      </Button>
    );
  }
  return (
    <Button size="lg" nativeButton={false} render={<Link href={user ? '/app/plan' : '/login'} />}>
      {user ? 'See your plan' : `Get Pro · ${PRICE.currency}${PRICE.pro}/month`}
    </Button>
  );
}
