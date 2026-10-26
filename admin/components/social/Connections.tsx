'use client';

import { useState } from 'react';

import { Badge, Card, ErrorNote, Loading, button } from '@/components/ui';
import { errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { PLATFORM_NAMES, startConnecting, useDisconnect, useSocialOverview } from '@/lib/social';
import type { SocialAccount, SocialProvider } from '@/lib/types';

const PROVIDERS: { provider: SocialProvider; label: string; covers: string }[] = [
  { provider: 'linkedin', label: 'LinkedIn', covers: 'Your LinkedIn profile' },
  {
    provider: 'meta',
    label: 'Facebook & Instagram',
    covers: 'Your Facebook Pages and the Instagram business accounts linked to them',
  },
];

const WARN_DAYS = 7;

function daysLeft(account: SocialAccount): number | null {
  if (!account.expires_at) return null;
  return Math.floor((new Date(account.expires_at).getTime() - Date.now()) / 86_400_000);
}

function AccountRow({ account }: { account: SocialAccount }) {
  const disconnect = useDisconnect();
  const [confirming, setConfirming] = useState(false);
  const left = daysLeft(account);
  const expired = account.status === 'expired' || (left !== null && left < 0);

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">
          {account.name}{' '}
          <span className="font-normal text-zinc-500">· {PLATFORM_NAMES[account.platform]}</span>
        </p>
        <p className="text-xs text-zinc-500">
          Connected by {account.connected_by} on {formatDateTime(account.created_at)}
        </p>
      </div>
      {expired ? (
        <Badge tone="red">Reconnect needed</Badge>
      ) : left !== null && left <= WARN_DAYS ? (
        <Badge tone="amber">
          Expires in {left} {left === 1 ? 'day' : 'days'}
        </Badge>
      ) : (
        <Badge tone="green">Connected</Badge>
      )}
      {confirming ? (
        <span className="flex items-center gap-2 text-sm">
          Disconnect? Posts already up stay up.
          <button
            onClick={() => disconnect.mutate(account.id)}
            disabled={disconnect.isPending}
            className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          >
            {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
          </button>
          <button onClick={() => setConfirming(false)} className={button}>
            Keep
          </button>
        </span>
      ) : (
        <button onClick={() => setConfirming(true)} className={button}>
          Disconnect
        </button>
      )}
      {disconnect.isError && (
        <p role="alert" className="w-full text-sm text-red-700">
          {errorMessage(disconnect.error)}
        </p>
      )}
    </li>
  );
}

export function Connections() {
  const overview = useSocialOverview();
  const [connecting, setConnecting] = useState<SocialProvider | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function connect(provider: SocialProvider) {
    setConnecting(provider);
    setError(null);
    try {
      await startConnecting(provider);
    } catch (caught) {
      setError(errorMessage(caught));
      setConnecting(null);
    }
  }

  return (
    <Card>
      <div className="border-b border-zinc-200 px-4 py-3">
        <h2 className="font-bold">Connected accounts</h2>
        <p className="text-sm text-zinc-500">
          Posts go out through each platform&apos;s official API. Reconnecting an account refreshes
          its login.
        </p>
      </div>
      {overview.isPending ? (
        <Loading rows={3} />
      ) : overview.isError ? (
        <ErrorNote message={errorMessage(overview.error)} onRetry={() => overview.refetch()} />
      ) : (
        <>
          <div className="grid gap-3 p-4 sm:grid-cols-2">
            {PROVIDERS.map(({ provider, label, covers }) => {
              const configured = overview.data.providers.find(
                (item) => item.provider === provider,
              )?.configured;
              return (
                <div key={provider} className="rounded-lg p-3 ring-1 ring-zinc-200">
                  <p className="text-sm font-semibold">{label}</p>
                  <p className="mt-0.5 text-xs text-zinc-500">{covers}</p>
                  <button
                    onClick={() => connect(provider)}
                    disabled={!configured || connecting !== null}
                    className="mt-3 rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
                  >
                    {connecting === provider ? 'Opening…' : `Connect ${label}`}
                  </button>
                  {!configured && (
                    <p className="mt-2 text-xs text-amber-700">
                      Not set up yet: add the app keys to the API&apos;s settings first.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          {error && (
            <p role="alert" className="px-4 pb-3 text-sm text-red-700">
              {error}
            </p>
          )}
          {overview.data.accounts.length > 0 ? (
            <ul className="divide-y divide-zinc-100 border-t border-zinc-200">
              {overview.data.accounts.map((account) => (
                <AccountRow key={account.id} account={account} />
              ))}
            </ul>
          ) : (
            <p className="border-t border-zinc-200 px-4 py-6 text-center text-sm text-zinc-500">
              No accounts connected yet. Connect one above to start posting.
            </p>
          )}
        </>
      )}
    </Card>
  );
}
