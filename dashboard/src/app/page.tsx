import { ArrowRight, ShieldCheck } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

import { FaqList } from '@/components/landing/faq';
import { FeatureShowcase } from '@/components/landing/feature-showcase';
import { HeroConsole } from '@/components/landing/hero-console';
import { JsonLd } from '@/components/landing/json-ld';
import { LandingCta } from '@/components/landing/landing-cta';
import { ResumeEditDemo } from '@/components/landing/resume-edit-demo';
import { Display, Eyebrow, Texture } from '@/components/brand/primitives';
import { SampleMatch } from '@/components/landing/sample-match';
import { SiteFooter } from '@/components/landing/site-footer';
import { SiteHeader } from '@/components/landing/site-header';
import {
  applicationData,
  faqData,
  graph,
  organisationData,
  websiteData,
} from '@/components/landing/structured-data';
import { buttonVariants } from '@/components/ui/button';
import { FEATURE_PAGES, featurePath, HOME_FAQS } from '@/content/marketing';
import { cn } from '@/lib/utils';

export const metadata: Metadata = { alternates: { canonical: '/' } };

const JOB_SITES = ['LinkedIn', 'Naukri', 'Indeed', 'Company career pages'] as const;

const SCORE_FACTS = [
  { title: 'Judged per skill', body: 'Strong, partial or missing.' },
  { title: 'Quoted evidence', body: 'Every verdict cites your profile.' },
  { title: 'Calculated score', body: 'Plain arithmetic on the verdicts.' },
  { title: 'No AI key needed', body: 'Job checks run without a model.' },
] as const;

const RESUME_FACTS = [
  { title: 'Your own file', body: 'Same fonts, spacing and layout.' },
  { title: 'Only what you tick', body: 'Skills you confirm you have.' },
  { title: 'History untouched', body: 'Titles, employers and dates stay.' },
  { title: 'Previewed first', body: 'Before and after, then download.' },
] as const;

const STEPS = [
  {
    title: 'Upload your resume',
    body: 'We turn it into a profile and an evidence bank you can review and correct.',
  },
  {
    title: 'Check any job',
    body: 'Paste a link, or open the job page and read your score beside the Apply button.',
  },
  {
    title: 'Match your resume and apply',
    body: "Tick the skills you really have to put them in the job's wording, then let autofill fill the form. You review it and submit.",
  },
  {
    title: 'Tracked for you',
    body: 'The job is saved when you press Apply and marked as applied when the site confirms it.',
  },
  {
    title: 'Replies move it forward',
    body: 'Connect Gmail with read-only access and interview invites, rejections and offers update the application for you.',
  },
] as const;

const PROMISES = [
  { label: 'Never', body: 'Submits an application for you.' },
  { label: 'Never', body: 'Sends an email for you.' },
  { label: 'Never', body: 'Adds a skill you did not tick.' },
  { label: 'Never', body: 'Changes a job title, employer or date on your resume.' },
  { label: 'Never', body: 'Overwrites what you typed into a form.' },
  { label: 'Not stored', body: 'A tailored resume is kept only if you choose to keep it.' },
  {
    label: 'Read-only',
    body: 'Gmail access cannot send or delete, and mail bodies are never stored.',
  },
  { label: 'Anytime', body: 'Download everything we hold about you as one file.' },
] as const;

const RAILS = 'mx-auto w-full max-w-6xl border-x border-dashed';
const GUTTER = 'px-5 sm:px-10 lg:px-16';

export default function LandingPage() {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col overflow-x-clip">
      <JsonLd
        data={graph(
          organisationData(),
          websiteData(),
          applicationData(FEATURE_PAGES.map((page) => page.summary)),
          faqData(HOME_FAQS),
        )}
      />
      <SiteHeader />

      <main className="flex-1">
        <section className="relative isolate overflow-hidden">
          <div
            aria-hidden
            className="from-background via-primary/30 to-primary absolute inset-0 -z-20 bg-linear-to-b from-20% via-60%"
          />
          <Texture className="-z-10 [mask-image:linear-gradient(to_bottom,transparent_50%,black_95%)] opacity-45" />

          <div className="mx-auto w-full max-w-6xl px-5 pt-20 pb-48 text-center sm:pt-28 sm:pb-64">
            <p className="text-foreground/70 text-sm font-medium">
              Job match score · Resume tailoring · Autofill · Application tracker
            </p>
            <Display as="h1" className="mx-auto mt-5 max-w-4xl sm:text-6xl lg:text-7xl">
              Know your fit <span className="text-primary">before you apply</span>
            </Display>
            <p className="text-foreground/75 mx-auto mt-6 max-w-xl text-lg text-pretty">
              Rolesetu scores any job description against your resume, puts the job&apos;s keywords
              into your own resume PDF, fills the application form, and tracks where each
              application stands.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <LandingCta />
              <a
                href="#how-it-works"
                className={cn(
                  buttonVariants({ variant: 'outline' }),
                  'bg-background/70 h-12 px-7 text-base backdrop-blur',
                )}
              >
                See how it works
              </a>
            </div>
            <div className="mt-10">
              <HeroConsole />
            </div>
          </div>
        </section>

        <div className={RAILS}>
          <section id="what" className={cn(GUTTER, 'scroll-mt-16 py-20 sm:py-28')}>
            <div className="max-w-3xl">
              <Eyebrow>What Rolesetu is</Eyebrow>
              <Display className="mt-6">
                <span className="block">One assistant for</span>
                <span className="text-primary block">the whole job application.</span>
              </Display>
              <p className="text-muted-foreground mt-6 text-lg text-pretty">
                Rolesetu is a web app and browser extension for people applying to jobs. Upload your
                resume once. For every job after that it tells you how well you fit and why, helps
                you put the job&apos;s wording into your resume, fills the application form, and
                keeps a record of what you applied to and what came back. It prepares the work; you
                decide what gets sent.
              </p>
            </div>

            <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURE_PAGES.map((page) => (
                <li key={page.slug}>
                  <Link
                    href={featurePath(page.slug)}
                    className="group bg-card hover:border-foreground/30 focus-visible:ring-ring/60 flex h-full flex-col rounded-2xl border p-5 transition-colors outline-none focus-visible:ring-2"
                  >
                    <h3 className="flex items-center justify-between gap-3 font-medium">
                      {page.name}
                      <ArrowRight className="text-muted-foreground size-4 shrink-0 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
                    </h3>
                    <p className="text-muted-foreground mt-2 text-sm">{page.summary}</p>
                  </Link>
                </li>
              ))}
            </ul>

            <div className="mt-12 flex flex-wrap items-center gap-x-3 gap-y-3 border-t pt-6 text-sm">
              <p className="text-muted-foreground mr-2">Reads jobs on</p>
              {JOB_SITES.map((site) => (
                <span key={site} className="bg-muted rounded-full px-3 py-1 font-medium">
                  {site}
                </span>
              ))}
              <p className="text-muted-foreground">or paste a link from anywhere else.</p>
            </div>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-20 sm:py-28')}>
            <div className="grid items-center gap-12 lg:grid-cols-[5fr_7fr] lg:gap-16">
              <div>
                <Display>
                  <span className="block">A score you can</span>
                  <span className="text-primary block">check line by line.</span>
                </Display>
                <p className="text-muted-foreground mt-6 max-w-md text-lg">
                  Each skill a job asks for is checked against your own profile and marked strong,
                  partial or missing. The number is worked out from those verdicts, so you can see
                  exactly where it came from.
                </p>
                <Link
                  href={featurePath('job-match-score')}
                  className="text-primary mt-7 inline-flex items-center gap-2 text-sm font-medium hover:underline"
                >
                  See how a job gets scored
                  <ArrowRight className="size-4" />
                </Link>
              </div>
              <div className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.5_0.24_292)] p-4 sm:p-8">
                <Texture className="-z-10 opacity-25" />
                <SampleMatch />
              </div>
            </div>

            <dl className="mt-16 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {SCORE_FACTS.map((fact) => (
                <div key={fact.title} className="border-t pt-4">
                  <dt className="text-sm font-medium">{fact.title}</dt>
                  <dd className="text-muted-foreground mt-1.5 text-sm">{fact.body}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section
            id="resume"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <div className="grid items-center gap-12 lg:grid-cols-[7fr_5fr] lg:gap-16">
              <div className="lg:order-last">
                <Eyebrow>Resume match</Eyebrow>
                <Display className="mt-6">
                  <span className="block">Still your resume.</span>
                  <span className="text-primary block">Now in the job&apos;s words.</span>
                </Display>
                <p className="text-muted-foreground mt-6 max-w-md text-lg">
                  We compare the job&apos;s wording with your resume and show what is missing or
                  written differently. Tick what is true and the PDF you uploaded is edited in
                  place, not rebuilt from a template.
                </p>
                <Link
                  href={featurePath('resume-keyword-match')}
                  className="text-primary mt-7 inline-flex items-center gap-2 text-sm font-medium hover:underline"
                >
                  See how resume tailoring works
                  <ArrowRight className="size-4" />
                </Link>
              </div>
              <div className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.43_0.11_155)] p-4 sm:p-8">
                <Texture className="-z-10 opacity-20" />
                <ResumeEditDemo />
              </div>
            </div>

            <dl className="mt-16 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {RESUME_FACTS.map((fact) => (
                <div key={fact.title} className="border-t pt-4">
                  <dt className="text-sm font-medium">{fact.title}</dt>
                  <dd className="text-muted-foreground mt-1.5 text-sm">{fact.body}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section
            id="features"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <div className="mx-auto max-w-3xl text-center">
              <Eyebrow>One profile, every step</Eyebrow>
              <Display className="mt-6">
                <span className="block">From finding a job</span>
                <span className="text-primary block">to hearing back.</span>
              </Display>
              <p className="text-muted-foreground mx-auto mt-5 max-w-xl text-lg">
                Your resume is read once. After that every tool works from the same profile and the
                same evidence.
              </p>
            </div>
            <div className="mt-14">
              <FeatureShowcase />
            </div>
          </section>

          <section
            id="how-it-works"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
              <div className="lg:sticky lg:top-28 lg:self-start">
                <Display>
                  <span className="block">From resume to reply</span>
                  <span className="text-primary block">in five steps.</span>
                </Display>
                <p className="text-muted-foreground mt-6 max-w-md text-lg">
                  Set up once. After that, each job takes a few seconds to check and a few clicks to
                  apply.
                </p>
              </div>
              <ol>
                {STEPS.map((step, index) => (
                  <li key={step.title} className="border-b py-8 first:pt-0 last:border-b-0">
                    <p className="text-muted-foreground/50 font-mono text-4xl tracking-tight">
                      0{index + 1}
                    </p>
                    <h3 className="mt-5 text-xl font-medium tracking-tight">{step.title}</h3>
                    <p className="text-muted-foreground mt-2 max-w-md">{step.body}</p>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        </div>

        <section id="control" className="dark bg-background text-foreground scroll-mt-16">
          <div className={cn(RAILS, GUTTER, 'py-20 sm:py-28')}>
            <Eyebrow>Your control</Eyebrow>
            <Display className="mt-6">
              <span className="block">It prepares the work.</span>
              <span className="text-muted-foreground block">You decide what gets sent.</span>
            </Display>

            <ul className="bg-border mt-14 grid gap-px overflow-hidden rounded-2xl border sm:grid-cols-2 lg:grid-cols-3">
              {PROMISES.map((promise) => (
                <li key={promise.body} className="bg-background flex min-h-40 flex-col p-6">
                  <p className="text-muted-foreground font-mono text-[0.6875rem] tracking-[0.14em] uppercase">
                    {promise.label}
                  </p>
                  <p className="mt-auto pt-8 text-lg leading-snug font-medium tracking-tight">
                    {promise.body}
                  </p>
                </li>
              ))}
              <li className="relative isolate flex min-h-40 flex-col overflow-hidden bg-[oklch(0.5_0.14_155)] p-6 sm:col-span-2 lg:col-span-1">
                <Texture className="-z-10 opacity-20" />
                <ShieldCheck className="size-5" />
                <p className="mt-auto pt-8 text-lg leading-snug font-medium tracking-tight">
                  Autofill and drafts only. The last click is always yours.
                </p>
              </li>
            </ul>
          </div>
        </section>

        <div className={RAILS}>
          <section id="faq" className={cn(GUTTER, 'scroll-mt-16 py-20 sm:py-28')}>
            <div className="grid gap-12 lg:grid-cols-[5fr_7fr] lg:gap-16">
              <Display>
                <span className="block">Questions,</span>
                <span className="text-primary block">answered plainly.</span>
              </Display>
              <FaqList faqs={HOME_FAQS} />
            </div>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-24 sm:py-32')}>
            <Display className="sm:text-6xl">
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
