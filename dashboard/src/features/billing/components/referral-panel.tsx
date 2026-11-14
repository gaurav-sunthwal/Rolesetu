'use client';

import { Check, Copy, Gift, Share2, Users } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { ReferralSteps } from '@/components/pricing/referral-steps';
import { SectionCard } from '@/components/app/section-card';
import { ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { CHECKS_TO_UNLOCK, PRICE } from '@/content/pricing';
import { inviteLink, type ReferralSummary, useReferrals } from '@/features/billing/referrals';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

const MESSAGE =
  'I use Rolesetu to see how well I match a job before applying, and it autofills applications. Try it free:';

const STATUS = {
  joined: { label: 'Joined', tone: 'bg-muted text-muted-foreground' },
  unlocked: {
    label: `${PRICE.currency}${PRICE.referral} month ready`,
    tone: 'bg-success/15 text-success',
  },
  used: { label: 'Discount used', tone: 'bg-primary/10 text-primary' },
} as const;

export function ReferralPanel() {
  const referrals = useReferrals();

  return (
    <SectionCard
      title={`Invite friends, pay ${PRICE.currency}${PRICE.referral}`}
      description={`When a friend joins with your link and starts using Rolesetu, your first Pro month is ${PRICE.currency}${PRICE.referral} instead of ${PRICE.currency}${PRICE.pro}.`}
    >
      {referrals.isPending ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-12 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
        </div>
      ) : referrals.isError ? (
        <ErrorState
          error={referrals.error}
          onRetry={() => void referrals.refetch()}
          className="py-6"
        />
      ) : (
        <ReferralDetails summary={referrals.data} />
      )}
      <ReferralSteps className="mt-6" />
    </SectionCard>
  );
}

function ReferralDetails({ summary }: { summary: ReferralSummary }) {
  const link = inviteLink(summary.code);
  const [copied, setCopied] = useState(false);
  const joined = summary.friends.length;
  const used = summary.friends.filter((friend) => friend.status === 'used').length;
  const shareText = `${MESSAGE} ${link}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      toast.success('Invite link copied.');
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy. Select the link and copy it yourself.');
    }
  }

  async function shareNatively() {
    try {
      await navigator.share({ title: 'Rolesetu', text: MESSAGE, url: link });
    } catch {
      // Closed the share sheet: nothing to do.
    }
  }

  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function';

  return (
    <div className="flex flex-col gap-6">
      <div>
        <label htmlFor="invite-link" className="text-sm font-medium">
          Your invite link
        </label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            id="invite-link"
            readOnly
            value={link}
            onFocus={(event) => event.currentTarget.select()}
            className="bg-muted/50 focus-visible:ring-ring/50 min-w-0 flex-1 rounded-full border px-4 py-2 font-mono text-sm outline-none focus-visible:ring-3"
          />
          <Button onClick={() => void copy()} className="shrink-0">
            {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
            {copied ? 'Copied' : 'Copy link'}
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            nativeButton={false}
            render={
              <a
                href={`https://wa.me/?text=${encodeURIComponent(shareText)}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            WhatsApp
          </Button>
          <Button
            variant="outline"
            size="sm"
            nativeButton={false}
            render={
              <a
                href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(link)}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            LinkedIn
          </Button>
          <Button
            variant="outline"
            size="sm"
            nativeButton={false}
            render={
              <a
                href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(MESSAGE)}&url=${encodeURIComponent(link)}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            X
          </Button>
          {canShare ? (
            <Button variant="outline" size="sm" onClick={() => void shareNatively()}>
              <Share2 aria-hidden />
              More
            </Button>
          ) : null}
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-2 text-center">
        <Stat
          label="Friends joined"
          value={joined}
          icon={<Users className="size-4" aria-hidden />}
        />
        <Stat
          label={`${PRICE.currency}${PRICE.referral} first month`}
          value={summary.rewards_available}
          icon={<Gift className="size-4" aria-hidden />}
          highlight={summary.rewards_available > 0}
        />
        <Stat label="Used" value={used} icon={<Check className="size-4" aria-hidden />} />
      </dl>

      {summary.rewards_available > 0 ? (
        <p className="bg-success/10 text-success rounded-2xl px-4 py-3 text-sm font-medium">
          Your first Pro month is {PRICE.currency}
          {PRICE.referral}. It is applied when you start autopay.
        </p>
      ) : null}

      {joined > 0 ? (
        <div>
          <h3 className="mb-2 text-sm font-medium">Friends</h3>
          <ul className="divide-y rounded-2xl border text-sm">
            {summary.friends.map((friend, index) => {
              const status = STATUS[friend.status];
              return (
                <li
                  key={`${friend.joined_at}-${index}`}
                  className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
                >
                  <span>
                    Friend {joined - index}
                    <span className="text-muted-foreground">
                      {' '}
                      · joined {formatDate(friend.joined_at)}
                    </span>
                  </span>
                  <span
                    className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', status.tone)}
                  >
                    {status.label}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="text-muted-foreground mt-2 text-xs">
            A friend unlocks your discount once they upload a resume and check {CHECKS_TO_UNLOCK}{' '}
            jobs. You never see their details, only how far they have got.
          </p>
        </div>
      ) : (
        <p className="text-muted-foreground rounded-2xl border border-dashed px-4 py-6 text-center text-sm">
          No friends yet. Share your link with someone who is job hunting: they get Rolesetu free,
          and you get a cheaper month.
        </p>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
  highlight,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div className={cn('rounded-2xl border p-3', highlight && 'border-success/40 bg-success/5')}>
      <dt className="text-muted-foreground flex items-center justify-center gap-1.5 text-xs">
        {icon}
        {label}
      </dt>
      <dd className="mt-1 text-2xl font-semibold">{value}</dd>
    </div>
  );
}
