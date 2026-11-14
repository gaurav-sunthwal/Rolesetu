import { Check, Crown, Minus } from 'lucide-react';
import type { ReactNode } from 'react';

import {
  CREDITS,
  FREE_POINTS,
  PLAN_ROWS,
  type PlanCell,
  PRICE,
  PRO_POINTS,
} from '@/content/pricing';
import { cn } from '@/lib/utils';

/**
 * Free and Pro side by side, then every feature in a table. Pure layout: the
 * landing page passes sign-up links, the dashboard passes the upgrade button.
 */
export function PlanComparison({
  freeAction,
  proAction,
  proPrice,
  proWasPrice,
  currentPlan,
}: {
  freeAction?: ReactNode;
  proAction?: ReactNode;
  /** What Pro costs this person, when it differs from the list price. */
  proPrice?: string;
  proWasPrice?: string;
  currentPlan?: 'free' | 'pro';
}) {
  return (
    <div className="flex flex-col gap-10">
      <div className="grid gap-4 md:grid-cols-2">
        <PlanCard
          name="Free"
          price={`${PRICE.currency}0`}
          period="forever"
          blurb="Everything you need to check jobs and apply faster."
          points={FREE_POINTS}
          action={freeAction}
          current={currentPlan === 'free'}
        />
        <PlanCard
          featured
          name="Pro"
          price={proPrice ?? `${PRICE.currency}${PRICE.pro}`}
          wasPrice={proWasPrice}
          period="a month"
          blurb="For an active job hunt, with AI on every application."
          points={PRO_POINTS}
          action={proAction}
          current={currentPlan === 'pro'}
          footnote={`Monthly autopay with UPI or card; cancel any time. Your first month is ${PRICE.currency}${PRICE.referral} when you bring a friend.`}
        />
      </div>

      <div className="overflow-hidden rounded-3xl border">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Free and Pro, feature by feature</caption>
          <thead className="bg-muted/50">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium sm:px-6">
                Feature
              </th>
              <th scope="col" className="w-24 px-3 py-3 text-center font-medium sm:w-40">
                Free
              </th>
              <th
                scope="col"
                className="text-primary w-24 px-3 py-3 text-center font-medium sm:w-40"
              >
                Pro
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {PLAN_ROWS.map((row) => (
              <tr key={row.feature}>
                <th scope="row" className="px-4 py-3.5 align-top font-normal sm:px-6">
                  <span className="font-medium">{row.feature}</span>
                  {row.detail ? (
                    <span className="text-muted-foreground mt-0.5 hidden text-xs sm:block">
                      {row.detail}
                    </span>
                  ) : null}
                </th>
                <td className="px-3 py-3.5 text-center align-top">
                  <Cell value={row.free} />
                </td>
                <td className="bg-primary/[0.03] px-3 py-3.5 text-center align-top">
                  <Cell value={row.pro} strong />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-muted-foreground -mt-6 text-xs">
        Credits come back on the 1st of every month. Everything that does not use AI is unlimited on
        both plans. Free has {CREDITS.free}, Pro has {CREDITS.pro}.
      </p>
    </div>
  );
}

function Cell({ value, strong }: { value: PlanCell; strong?: boolean }) {
  if (value === true) {
    return (
      <>
        <Check className={cn('mx-auto size-4', strong && 'text-primary')} aria-hidden />
        <span className="sr-only">Included</span>
      </>
    );
  }
  if (value === false) {
    return (
      <>
        <Minus className="text-muted-foreground mx-auto size-4" aria-hidden />
        <span className="sr-only">Not included</span>
      </>
    );
  }
  return <span className={cn(strong && 'text-primary font-medium')}>{value}</span>;
}

function PlanCard({
  name,
  price,
  wasPrice,
  period,
  blurb,
  points,
  action,
  featured,
  current,
  footnote,
}: {
  name: string;
  price: string;
  wasPrice?: string;
  period: string;
  blurb: string;
  points: readonly string[];
  action?: ReactNode;
  featured?: boolean;
  current?: boolean;
  footnote?: string;
}) {
  return (
    <section
      aria-label={`${name} plan`}
      className={cn(
        'relative flex flex-col rounded-3xl border p-6 sm:p-8',
        featured ? 'border-primary/40 bg-primary/[0.04] shadow-sm' : 'bg-card',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-lg font-semibold">
          {featured ? <Crown className="text-primary size-5" aria-hidden /> : null}
          {name}
        </h3>
        {current ? (
          <span className="bg-primary text-primary-foreground rounded-full px-2.5 py-0.5 text-xs font-medium">
            Your plan
          </span>
        ) : featured ? (
          <span className="text-primary bg-primary/10 rounded-full px-2.5 py-0.5 text-xs font-medium">
            Most value
          </span>
        ) : null}
      </div>
      <p className="mt-5 flex items-baseline gap-2">
        <span className="text-4xl font-semibold tracking-tight">{price}</span>
        {wasPrice ? (
          <span className="text-muted-foreground text-lg line-through">{wasPrice}</span>
        ) : null}
        <span className="text-muted-foreground text-sm">{period}</span>
      </p>
      <p className="text-muted-foreground mt-2 text-sm">{blurb}</p>
      <ul className="mt-6 flex flex-col gap-2.5 text-sm">
        {points.map((point) => (
          <li key={point} className="flex items-start gap-2.5">
            <Check
              className={cn('mt-0.5 size-4 shrink-0', featured ? 'text-primary' : '')}
              aria-hidden
            />
            <span>{point}</span>
          </li>
        ))}
      </ul>
      {action ? <div className="mt-8 flex flex-col gap-2 pt-2 [&>*]:w-full">{action}</div> : null}
      {footnote ? <p className="text-muted-foreground mt-3 text-xs">{footnote}</p> : null}
    </section>
  );
}
