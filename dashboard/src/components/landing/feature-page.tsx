import { ArrowRight, ChevronRight } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

import { Display, Eyebrow } from '@/components/brand/primitives';
import { FaqList } from '@/components/landing/faq';
import { JsonLd } from '@/components/landing/json-ld';
import { LandingCta } from '@/components/landing/landing-cta';
import { SiteFooter } from '@/components/landing/site-footer';
import { SiteHeader } from '@/components/landing/site-header';
import { breadcrumbData, faqData, graph } from '@/components/landing/structured-data';
import { FEATURE_PAGES, featurePage, featurePath } from '@/content/marketing';
import { absoluteUrl, SITE } from '@/lib/site';
import { cn } from '@/lib/utils';

const RAILS = 'mx-auto w-full max-w-6xl border-x border-dashed';
const GUTTER = 'px-5 sm:px-10 lg:px-16';

export function featureMetadata(slug: string): Metadata {
  const page = featurePage(slug);
  const path = featurePath(slug);
  return {
    title: page.title,
    description: page.description,
    alternates: { canonical: path },
    // A page that sets its own Open Graph fields replaces the site-wide ones, so
    // the shared preview image and site name are named again here.
    openGraph: {
      type: 'article',
      siteName: SITE.name,
      locale: 'en_US',
      url: path,
      title: page.title,
      description: page.description,
      images: [{ url: '/opengraph-image.png', width: 1200, height: 630, alt: SITE.tagline }],
    },
    twitter: {
      card: 'summary_large_image',
      title: page.title,
      description: page.description,
      images: ['/twitter-image.png'],
    },
  };
}

/** One public page per feature, so each can be found by the search it answers. */
export function FeaturePageView({ slug }: { slug: string }) {
  const page = featurePage(slug);
  const path = featurePath(slug);
  const others = FEATURE_PAGES.filter((item) => item.slug !== slug);

  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col overflow-x-clip">
      <JsonLd
        data={graph(
          {
            '@type': 'WebPage',
            '@id': absoluteUrl(path),
            url: absoluteUrl(path),
            name: page.title,
            description: page.description,
            dateModified: SITE.updated,
            isPartOf: { '@id': `${SITE.url}/#website` },
            about: { '@id': `${SITE.url}/#application` },
          },
          breadcrumbData([
            { name: 'Home', path: '/' },
            { name: page.name, path },
          ]),
          faqData(page.faqs),
        )}
      />
      <SiteHeader />

      <main className="flex-1">
        <div className={RAILS}>
          <section className={cn(GUTTER, 'pt-12 pb-20 sm:pt-16 sm:pb-24')}>
            <nav aria-label="Breadcrumb" className="text-muted-foreground text-sm">
              <ol className="flex flex-wrap items-center gap-1.5">
                <li>
                  <Link href="/" className="hover:text-foreground transition-colors">
                    Home
                  </Link>
                </li>
                <ChevronRight aria-hidden className="size-3.5" />
                <li aria-current="page" className="text-foreground">
                  {page.name}
                </li>
              </ol>
            </nav>
            <Display as="h1" className="mt-8 max-w-3xl sm:text-6xl">
              {page.heading}
            </Display>
            <p className="text-muted-foreground mt-6 max-w-2xl text-lg text-pretty">{page.intro}</p>
            <div className="mt-9">
              <LandingCta />
            </div>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-20 sm:py-24')}>
            <Eyebrow>How it works</Eyebrow>
            <ol className="mt-10 grid gap-10 md:grid-cols-3">
              {page.steps.map((step, index) => (
                <li key={step.title} className="border-t pt-5">
                  <p className="text-muted-foreground/50 font-mono text-3xl tracking-tight">
                    0{index + 1}
                  </p>
                  <h2 className="mt-4 text-xl font-medium tracking-tight">{step.title}</h2>
                  <p className="text-muted-foreground mt-2">{step.body}</p>
                </li>
              ))}
            </ol>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-20 sm:py-24')}>
            <Eyebrow>What you get</Eyebrow>
            <dl className="mt-10 grid gap-x-12 gap-y-10 md:grid-cols-2">
              {page.details.map((detail) => (
                <div key={detail.title}>
                  <dt className="text-xl font-medium tracking-tight">{detail.title}</dt>
                  <dd className="text-muted-foreground mt-2 text-pretty">{detail.body}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-20 sm:py-24')}>
            <Display>Questions about {page.name.toLowerCase()}</Display>
            <div className="mt-10">
              <FaqList faqs={page.faqs} />
            </div>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-20 sm:py-24')}>
            <h2 className="text-xl font-medium tracking-tight">More from Rolesetu</h2>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {others.map((other) => (
                <li key={other.slug}>
                  <Link
                    href={featurePath(other.slug)}
                    className="group bg-card hover:border-foreground/30 focus-visible:ring-ring/60 flex h-full flex-col rounded-2xl border p-5 transition-colors outline-none focus-visible:ring-2"
                  >
                    <span className="flex items-center justify-between gap-3 font-medium">
                      {other.name}
                      <ArrowRight className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
                    </span>
                    <span className="text-muted-foreground mt-2 text-sm">{other.summary}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-24 sm:py-28')}>
            <Display>
              <span className="block">Stop guessing which jobs</span>
              <span className="text-primary block">are worth your time.</span>
            </Display>
            <p className="text-muted-foreground mt-6 max-w-md text-lg">
              Upload your resume and check your first job in a couple of minutes.
            </p>
            <div className="mt-9">
              <LandingCta />
            </div>
          </section>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
