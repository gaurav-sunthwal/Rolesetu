import Link from 'next/link';

import { NAV_LINKS } from '@/components/landing/site-header';
import { Logo } from '@/components/logo';
import { FEATURE_PAGES, featurePath } from '@/content/marketing';

// Padded so each link is a comfortable target for a thumb.
const LINK = 'text-foreground/70 hover:text-foreground inline-block py-2 transition-colors';

export function SiteFooter() {
  return (
    <footer className="overflow-hidden border-t">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-5 pt-12 md:grid-cols-[2fr_1fr_1fr]">
        <div>
          <Logo />
          <p className="text-muted-foreground mt-3 max-w-xs text-sm">
            A job match score, resume tailoring, application autofill and a tracker, built for job
            seekers who would rather apply well than apply often.
          </p>
        </div>
        <nav aria-label="Product">
          <h2 className="text-sm font-medium">Product</h2>
          <ul className="mt-2 text-sm">
            {FEATURE_PAGES.map((page) => (
              <li key={page.slug}>
                <Link href={featurePath(page.slug)} className={LINK}>
                  {page.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <nav aria-label="Rolesetu">
          <h2 className="text-sm font-medium">Rolesetu</h2>
          <ul className="mt-2 text-sm">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className={LINK}>
                  {link.label}
                </Link>
              </li>
            ))}
            <li>
              <Link href="/privacy" className={LINK}>
                Privacy
              </Link>
            </li>
            <li>
              <Link href="/login" className={LINK}>
                Log in
              </Link>
            </li>
          </ul>
        </nav>
      </div>
      <p
        aria-hidden
        className="text-foreground/6 mt-8 -mb-[4vw] text-center text-[17vw] leading-none font-semibold tracking-[-0.06em] select-none"
      >
        Rolesetu
      </p>
    </footer>
  );
}
