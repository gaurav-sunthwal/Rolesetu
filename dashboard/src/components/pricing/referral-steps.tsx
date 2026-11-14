import { Gift, Send, UserCheck } from 'lucide-react';

import { REFERRAL_STEPS } from '@/content/pricing';
import { cn } from '@/lib/utils';

const ICONS = [Send, UserCheck, Gift] as const;

/** How inviting a friend lowers your price, in three steps. */
export function ReferralSteps({ className }: { className?: string }) {
  return (
    <ol className={cn('grid gap-3 md:grid-cols-3', className)}>
      {REFERRAL_STEPS.map((step, index) => {
        const Icon = ICONS[index] ?? Gift;
        return (
          <li
            key={step.title}
            className="bg-card relative flex flex-col rounded-3xl border p-5 sm:p-6"
          >
            <div className="flex items-center gap-3">
              <span className="bg-primary/10 text-primary flex size-10 items-center justify-center rounded-full">
                <Icon className="size-5" aria-hidden />
              </span>
              <span className="text-muted-foreground font-mono text-[0.6875rem] tracking-[0.14em] uppercase">
                Step {index + 1}
              </span>
            </div>
            <p className="mt-5 font-semibold">{step.title}</p>
            <p className="text-muted-foreground mt-1.5 text-sm">{step.body}</p>
          </li>
        );
      })}
    </ol>
  );
}
