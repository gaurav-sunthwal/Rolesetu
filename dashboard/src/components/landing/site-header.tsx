import Link from 'next/link';

import { LandingCta, LandingLoginLink } from '@/components/landing/landing-cta';
import { ThemeToggle } from '@/components/layout/theme-toggle';
import { Logo } from '@/components/logo';

// Addressed from the root, so the same menu works on every public page.
export const NAV_LINKS = [
  { href: '/#features', label: 'Features' },
  { href: '/#resume', label: 'Resume match' },
  { href: '/#how-it-works', label: 'How it works' },
  { href: '/#faq', label: 'FAQ' },
] as const;

export function SiteHeader() {
  return (
    <header className="header-edge bg-background/85 sticky top-0 z-40 border-b border-transparent backdrop-blur-lg">
      <div className="relative mx-auto flex h-16 w-full max-w-6xl items-center px-5">
        <Link href="/" aria-label="Rolesetu home">
          <Logo />
        </Link>
        <nav
          aria-label="Main"
          className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-8 text-sm font-medium md:flex"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-foreground/70 hover:text-foreground transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <LandingLoginLink />
          <LandingCta size="nav" />
        </div>
      </div>
    </header>
  );
}
