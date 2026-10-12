import { ChevronRight } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

import { Display } from '@/components/brand/primitives';
import { SiteFooter } from '@/components/landing/site-footer';
import { SiteHeader } from '@/components/landing/site-header';
import { PRIVACY_INTRO, PRIVACY_SECTIONS } from '@/content/privacy';
import { SITE } from '@/lib/site';

const PATH = '/privacy';
const DESCRIPTION =
  'What data the Rolesetu web app and Chrome extension handle, why, where it is kept, and how to export or delete it.';

export const metadata: Metadata = {
  title: 'Privacy policy',
  description: DESCRIPTION,
  alternates: { canonical: PATH },
};

const UPDATED = new Date(`${SITE.updated}T00:00:00Z`).toLocaleDateString('en-GB', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
});

export default function Page() {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col overflow-x-clip">
      <SiteHeader />

      <main className="flex-1">
        <div className="mx-auto w-full max-w-6xl border-x border-dashed">
          <article className="px-5 pt-12 pb-20 sm:px-10 sm:pt-16 sm:pb-24 lg:px-16">
            <nav aria-label="Breadcrumb" className="text-muted-foreground text-sm">
              <ol className="flex flex-wrap items-center gap-1.5">
                <li>
                  <Link href="/" className="hover:text-foreground transition-colors">
                    Home
                  </Link>
                </li>
                <ChevronRight aria-hidden className="size-3.5" />
                <li aria-current="page" className="text-foreground">
                  Privacy policy
                </li>
              </ol>
            </nav>
            <Display as="h1" className="mt-8 max-w-3xl sm:text-6xl">
              Privacy policy
            </Display>
            <p className="text-muted-foreground mt-4 text-sm">
              Last updated <time dateTime={SITE.updated}>{UPDATED}</time>
            </p>
            <p className="text-muted-foreground mt-6 max-w-2xl text-lg text-pretty">
              {PRIVACY_INTRO}
            </p>

            <div className="mt-14 max-w-2xl space-y-12">
              {PRIVACY_SECTIONS.map((section) => (
                <section key={section.title}>
                  <h2 className="text-xl font-medium tracking-tight">{section.title}</h2>
                  {section.paragraphs?.map((paragraph) => (
                    <p key={paragraph} className="text-muted-foreground mt-3 text-pretty">
                      {paragraph}
                    </p>
                  ))}
                  {section.items && (
                    <ul className="text-muted-foreground mt-3 list-disc space-y-2 pl-5 text-pretty">
                      {section.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                </section>
              ))}

              <section>
                <h2 className="text-xl font-medium tracking-tight">Contact</h2>
                <p className="text-muted-foreground mt-3 text-pretty">
                  Questions about this policy, or a request to delete your account, go to{' '}
                  <a
                    href={`mailto:${SITE.contactEmail}`}
                    className="text-foreground underline underline-offset-4"
                  >
                    {SITE.contactEmail}
                  </a>
                  .
                </p>
              </section>
            </div>
          </article>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
