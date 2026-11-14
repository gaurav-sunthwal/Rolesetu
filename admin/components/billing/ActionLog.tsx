import Link from 'next/link';

import { Empty, td, th } from '@/components/ui';
import { formatDateTime, formatMoney } from '@/lib/format';
import type { BillingAction } from '@/lib/types';

const WHAT: Record<string, string> = {
  grant: 'Gave Pro',
  refund: 'Refunded',
  revoke: 'Removed a month',
  end_pro: 'Ended Pro',
  price: 'Changed the price',
};

function detail(action: BillingAction): string {
  const parts = [];
  if (action.days) parts.push(`${action.days} days`);
  if (action.amount) parts.push(formatMoney(action.amount));
  return parts.join(' · ');
}

/** Every change an admin made to payments, Pro or prices: who, what, why. */
export function ActionLog({
  actions,
  showUser = true,
}: {
  actions: BillingAction[];
  showUser?: boolean;
}) {
  if (actions.length === 0) return <Empty>No changes by admins yet.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-y border-zinc-200">
          <tr>
            <th className={th}>When</th>
            <th className={th}>What</th>
            {showUser && <th className={th}>User</th>}
            <th className={th}>Why</th>
            <th className={th}>By</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {actions.map((action) => (
            <tr key={action.id}>
              <td className={`${td} whitespace-nowrap`}>{formatDateTime(action.created_at)}</td>
              <td className={td}>
                <span className="font-semibold">{WHAT[action.action] ?? action.action}</span>
                {detail(action) && <span className="text-zinc-500"> · {detail(action)}</span>}
              </td>
              {showUser && (
                <td className={td}>
                  {action.user_id ? (
                    <Link href={`/users/${action.user_id}`} className="hover:underline">
                      {action.user_email ?? 'Deleted user'}
                    </Link>
                  ) : (
                    '–'
                  )}
                </td>
              )}
              <td className={`${td} text-zinc-600`}>{action.note ?? '–'}</td>
              <td className={`${td} text-zinc-600`}>{action.admin_email}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
