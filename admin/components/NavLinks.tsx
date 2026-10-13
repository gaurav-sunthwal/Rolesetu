'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LINKS = [
  { href: '/', label: 'Dashboard' },
  { href: '/users', label: 'Users' },
  { href: '/waitlist', label: 'Waiting list' },
  { href: '/audit', label: 'Audit log' },
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
