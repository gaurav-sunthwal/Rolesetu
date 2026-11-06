'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { SOCIAL_ENABLED } from '@/lib/features';

const LINKS = [
  { href: '/', label: 'Dashboard' },
  { href: '/activity', label: 'Activity' },
  { href: '/users', label: 'Users' },
  { href: '/job-checks', label: 'Job checks' },
  { href: '/applications', label: 'Applications' },
  { href: '/previews', label: 'Landing previews' },
  ...(SOCIAL_ENABLED ? [{ href: '/social', label: 'Social' }] : []),
  { href: '/waitlist', label: 'Waiting list' },
  { href: '/skill-catalogs', label: 'Skill catalogs' },
  { href: '/ai-calls', label: 'AI calls' },
  { href: '/errors', label: 'Errors' },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="mt-8 space-y-1" aria-label="Admin">
      {LINKS.map((l) => {
        const active = l.href === '/' ? pathname === '/' : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? 'page' : undefined}
            className={`block rounded-lg px-3 py-2 text-sm font-semibold ${active ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900'}`}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
