import { ArrowRight, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

import { FeatureShowcase } from '@/components/landing/feature-showcase';
import { HeroConsole } from '@/components/landing/hero-console';
import { LandingCta, LandingLoginLink } from '@/components/landing/landing-cta';
import { ResumeEditDemo } from '@/components/landing/resume-edit-demo';
import { Display, Eyebrow, Texture } from '@/components/brand/primitives';
import { SampleMatch } from '@/components/landing/sample-match';
import { ThemeToggle } from '@/components/layout/theme-toggle';
import { Logo } from '@/components/logo';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const NAV_LINKS = [
  { href: '#resume', label: 'Resume match' },
  { href: '#features', label: 'Features' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#control', label: 'Your control' },
] as const;

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
] as const;

const PROMISES = [
  { label: 'Never', body: 'Submits an application for you.' },
  { label: 'Never', body: 'Sends an email for you.' },
  { label: 'Never', body: 'Adds a skill you did not tick.' },
  { label: 'Never', body: 'Changes a job title, employer or date on your resume.' },
  { label: 'Never', body: 'Overwrites what you typed into a form.' },
  { label: 'Not stored', body: 'A tailored resume is kept only if you choose to keep it.' },
  { label: 'Anytime', body: 'Download everything we hold about you as one file.' },
] as const;

const RAILS = 'mx-auto w-full max-w-6xl border-x border-dashed';
const GUTTER = 'px-5 sm:px-10 lg:px-16';

export default function LandingPage() {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col overflow-x-clip">
      <header className="bg-background/85 sticky top-0 z-40 backdrop-blur-lg">
        <div className="relative mx-auto flex h-16 w-full max-w-6xl items-center px-5">
          <Link href="/" aria-label="Rolesetu home">
            <Logo />
          </Link>
          <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-8 text-sm font-medium md:flex">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-foreground/70 hover:text-foreground transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <LandingLoginLink />
            <LandingCta size="nav" />
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative isolate overflow-hidden">
          <div
            aria-hidden
            className="from-background via-primary/30 to-primary absolute inset-0 -z-20 bg-linear-to-b from-20% via-60%"
          />
          <Texture className="-z-10 [mask-image:linear-gradient(to_bottom,transparent_50%,black_95%)] opacity-45" />

          <div className="mx-auto w-full max-w-6xl px-5 pt-20 pb-48 text-center sm:pt-28 sm:pb-64">
            <p className="text-foreground/70 text-sm font-medium">
              Score it. Match your resume. Apply. Track it.
            </p>
            <Display as="h1" className="mx-auto mt-5 max-w-4xl sm:text-6xl lg:text-7xl">
              Know your fit <span className="text-primary">before you apply</span>
            </Display>
            <p className="text-foreground/75 mx-auto mt-6 max-w-xl text-lg text-pretty">
              Rolesetu scores any job against your real experience, puts its wording into your own
              resume, fills the application, and tracks where each one stands.
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
          <section className={cn(GUTTER, 'py-20 sm:py-28')}>
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
                <a
                  href="#how-it-works"
                  className="text-primary mt-7 inline-flex items-center gap-2 text-sm font-medium hover:underline"
                >
                  See how a job gets scored
                  <ArrowRight className="size-4" />
                </a>
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
                <Eyebrow>New</Eyebrow>
                <Display className="mt-6">
                  <span className="block">Still your resume.</span>
                  <span className="text-primary block">Now in the job&apos;s words.</span>
                </Display>
                <p className="text-muted-foreground mt-6 max-w-md text-lg">
                  We compare the job&apos;s wording with your resume and show what is missing or
                  written differently. Tick what is true and the PDF you uploaded is edited in
                  place, not rebuilt from a template.
                </p>
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
                  <span className="text-primary block">in four steps.</span>
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
              <li className="relative isolate flex min-h-40 flex-col overflow-hidden bg-[oklch(0.5_0.14_155)] p-6 lg:col-span-2">
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
          <section className={cn(GUTTER, 'py-24 sm:py-32')}>
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

      <footer className="overflow-hidden border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 pt-10 md:flex-row md:items-center md:justify-between">
          <div>
            <Logo />
            <p className="text-muted-foreground mt-3 max-w-xs text-sm">
              Built for job seekers who would rather apply well than apply often.
            </p>
          </div>
          <nav className="flex flex-wrap gap-x-8 gap-y-2 text-sm font-medium">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-foreground/70 hover:text-foreground transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>
        <p
          aria-hidden
          className="text-foreground/6 mt-6 -mb-[4vw] text-center text-[17vw] leading-none font-semibold tracking-[-0.06em] select-none"
        >
          Rolesetu
        </p>
      </footer>
    </div>
  );
}
