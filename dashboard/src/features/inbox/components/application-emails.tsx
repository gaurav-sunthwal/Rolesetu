'use client';

import { ExternalLink, Mail } from 'lucide-react';

import { Skeleton } from '@/components/ui/skeleton';
import type { InboxEmail } from '@/features/inbox/api';
import { useApplicationEmails } from '@/features/inbox/hooks';
import { formatDate } from '@/lib/format';

const KIND: Record<InboxEmail['kind'], string> = {
  applied: 'Application received',
  rejected: 'Rejected',
  interview: 'Interview',
  assessment: 'Assessment',
  offer: 'Offer',
  unclear: 'Not sure',
};

/**
 * The mails about one application, each with a link that opens it in Gmail.
 * Shows nothing when there are none (the application was tracked by hand, or
 * Gmail is not connected).
 */
export function ApplicationEmails({ applicationId }: { applicationId: string }) {
  const emails = useApplicationEmails(applicationId);
  if (emails.isPending) return <Skeleton className="h-16 w-full rounded-2xl" />;
  if (emails.isError || emails.data.length === 0) return null;

  return (
    <section>
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <Mail className="text-muted-foreground size-4" />
        Emails about this application
      </h3>
      <ul className="mt-3 flex flex-col gap-2">
        {emails.data.map((email) => (
          <li key={email.id} className="bg-secondary/60 rounded-2xl px-3.5 py-3">
            <p className="text-sm font-medium">{email.subject}</p>
            <p className="text-muted-foreground mt-0.5 text-xs">
              {KIND[email.kind]} · {email.sender_name} · {formatDate(email.received_at)}
            </p>
            {email.gmail_url ? (
              <a
                href={email.gmail_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary mt-2 inline-flex items-center gap-1 text-xs font-medium underline-offset-4 hover:underline"
              >
                Open in Gmail
                <ExternalLink className="size-3" />
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
