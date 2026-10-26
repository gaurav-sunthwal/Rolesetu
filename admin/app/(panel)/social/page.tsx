'use client';

import { notFound, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

import { Connections } from '@/components/social/Connections';
import { PostComposer } from '@/components/social/PostComposer';
import { PostQueue } from '@/components/social/PostQueue';
import { PageHeader } from '@/components/ui';
import { SOCIAL_ENABLED } from '@/lib/features';
import { useSocialOverview } from '@/lib/social';
import type { SocialPost } from '@/lib/types';

const RESULTS: Record<string, { tone: 'good' | 'bad'; text: string }> = {
  connected: { tone: 'good', text: 'Connected. The accounts are listed below.' },
  none: {
    tone: 'bad',
    text: 'The login worked, but it gave no account to post to. For Facebook and Instagram, choose your Page on the consent screen, and make sure Instagram is a business account linked to that Page.',
  },
  denied: { tone: 'bad', text: 'The connection was cancelled on the platform. Nothing changed.' },
  expired: {
    tone: 'bad',
    text: 'That connection took too long or came from an account that is not an admin. Start again.',
  },
  refused: {
    tone: 'bad',
    text: 'The platform refused the connection. Check the app settings (redirect address and permissions) and try again.',
  },
  failed: { tone: 'bad', text: 'Connecting failed on our side. Try again in a minute.' },
};

/** What happened on the platform's consent screen, shown once the browser comes back. */
function ConnectResult() {
  const params = useSearchParams();
  const result = RESULTS[params.get('result') ?? ''];
  if (!result) return null;
  return (
    <p
      role="status"
      className={`rounded-lg px-4 py-3 text-sm ring-1 ${result.tone === 'good' ? 'bg-emerald-50 text-emerald-900 ring-emerald-200' : 'bg-amber-50 text-amber-900 ring-amber-200'}`}
    >
      {result.text}
    </p>
  );
}

export default function SocialPage() {
  if (!SOCIAL_ENABLED) notFound();
  return <SocialSection />;
}

function SocialSection() {
  const overview = useSocialOverview();
  const [editing, setEditing] = useState<SocialPost | null>(null);

  return (
    <>
      <PageHeader
        title="Social"
        subtitle="Connect accounts, write posts, approve them, and they go out on time."
      />
      <div className="space-y-6">
        <Suspense fallback={null}>
          <ConnectResult />
        </Suspense>
        <Connections />
        <PostComposer
          // A new key resets the form when a different draft is opened.
          key={editing?.id ?? 'new'}
          accounts={overview.data?.accounts ?? []}
          editing={editing}
          onDone={() => setEditing(null)}
        />
        <PostQueue
          onEdit={(post) => {
            setEditing(post);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
        />
      </div>
    </>
  );
}
