import { ArrowRight } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Suspense } from 'react';

import { Display, Eyebrow } from '@/components/brand/primitives';
import { LandingCta } from '@/components/landing/landing-cta';
import { SiteFooter } from '@/components/landing/site-footer';
import { SiteHeader } from '@/components/landing/site-header';
import { Skeleton } from '@/components/ui/skeleton';
import { ScoreRing } from '@/features/matches/components/score-ring';
import { bandOf } from '@/features/matches/score';
import { getPublicShare, jobLine } from '@/features/share/public-share';
import { featurePath } from '@/content/marketing';
import { SITE } from '@/lib/site';
import { cn } from '@/lib/utils';

export async function generateMetadata({ params }: PageProps<'/s/[slug]'>): Promise<Metadata> {
  const { slug } = await params;
  const lookup = await getPublicShare(slug);
  // Shared cards are for people following a link, not for search results;
  // links on them still count, so crawlers may follow them.
  const robots = { index: false, follow: true };
  if (lookup.state !== 'found') return { title: 'Shared match score', robots };
  const { card } = lookup;
  const title = `${card.score}% match for ${jobLine(card)}`;
  const description = card.matched.length
    ? `Matched ${card.matched.slice(0, 4).join(', ')}. Check your own resume against any job, free.`
    : 'Check your own resume against any job posting, free.';
  return {
    title,
    description,
    robots,
    alternates: { canonical: `/s/${slug}` },
    openGraph: { type: 'website', siteName: SITE.name, url: `/s/${slug}`, title, description },
    twitter: { card: 'summary_large_image', title, description },
  };
}

export default function SharedScorePage({ params }: PageProps<'/s/[slug]'>) {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col overflow-x-clip">
      <SiteHeader />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6 sm:py-16">
        <Suspense fallback={<CardSkeleton />}>
          {params.then(({ slug }) => (
            <SharedCard slug={slug} />
          ))}
        </Suspense>
        <section className="mt-14 border-t border-dashed pt-10">
          <Eyebrow>How the score works</Eyebrow>
          <p className="text-muted-foreground mt-4 text-pretty">
            Rolesetu reads the job posting, checks every skill it asks for against the person&apos;s
            own resume, and points at the line that proves each one. The number is worked out from
            those checks with a fixed formula, so it explains itself.
          </p>
          <Link
            href={featurePath('job-match-score')}
            className="text-primary mt-4 inline-flex items-center gap-1 text-sm font-medium underline-offset-4 hover:underline"
          >
            More about the match score
            <ArrowRight className="size-3.5" />
          </Link>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

async function SharedCard({ slug }: { slug: string }) {
  const lookup = await getPublicShare(slug);
  if (lookup.state === 'unavailable') {
    return (
      <Notice
        title="This score could not be loaded right now"
        body="Our server did not answer. Refresh the page in a moment."
      />
    );
  }
  if (lookup.state === 'missing') {
    return (
      <Notice
        title="This shared score was taken down"
        body="The person who shared it removed the link. You can still check your own fit for any job."
      />
    );
  }

  const { card } = lookup;
  const band = bandOf(card.score);
  return (
    <article className="bg-card rounded-4xl border p-6 sm:p-10">
      <div className="flex flex-col items-center gap-6 text-center sm:flex-row sm:text-left">
        <ScoreRing score={card.score} />
        <div className="min-w-0">
          <p className={cn('text-sm font-semibold', band.text)}>{band.label}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-balance sm:text-3xl">
            {card.score}% match for {jobLine(card)}
          </h1>
          <p className="text-muted-foreground mt-2 text-sm">
            Someone checked their resume against this job with Rolesetu and chose to share the
            result.
          </p>
        </div>
      </div>

      {card.matched.length > 0 ? (
        <SkillList label="Skills they showed" skills={card.matched} tone="matched" />
      ) : null}
      {card.gaps.length > 0 ? (
        <SkillList label="Still to show" skills={card.gaps} tone="gap" />
      ) : null}

      <div className="mt-8 flex flex-col items-center gap-3 border-t pt-8 sm:flex-row">
        <p className="flex-1 text-center font-medium sm:text-left">
          How well does your resume fit the jobs you want?
        </p>
        <LandingCta />
      </div>
    </article>
  );
}

function SkillList({
  label,
  skills,
  tone,
}: {
  label: string;
  skills: string[];
  tone: 'matched' | 'gap';
}) {
  return (
    <div className="mt-8">
      <h2 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        {label}
      </h2>
      <ul className="mt-3 flex flex-wrap gap-2">
        {skills.map((skill) => (
          <li
            key={skill}
            className={cn(
              'rounded-full px-3 py-1 text-sm font-medium',
              tone === 'matched' ? 'bg-success/15 text-foreground' : 'bg-secondary',
            )}
          >
            {skill}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Notice({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-card rounded-4xl border p-8 text-center sm:p-12">
      <Display as="h1" className="text-3xl sm:text-4xl">
        {title}
      </Display>
      <p className="text-muted-foreground mx-auto mt-4 max-w-md">{body}</p>
      <div className="mt-8 flex justify-center">
        <LandingCta />
      </div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="bg-card rounded-4xl border p-6 sm:p-10" aria-busy="true" aria-label="Loading">
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <Skeleton className="size-36 rounded-full" />
        <div className="flex w-full flex-col gap-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    </div>
  );
}
