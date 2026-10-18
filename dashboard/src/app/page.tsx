import { ArrowRight, ShieldCheck } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

import { ExtensionSection } from '@/components/landing/extension-section';
import { FaqList } from '@/components/landing/faq';
import { FeatureShowcase } from '@/components/landing/feature-showcase';
import { HeroJobCheck } from '@/components/landing/hero-job-check';
import { JsonLd } from '@/components/landing/json-ld';
import { LandingCta } from '@/components/landing/landing-cta';
import { FreshJobsDemo } from '@/components/landing/fresh-jobs-demo';
import { ResumeAssistantDemo } from '@/components/landing/resume-assistant-demo';
import { ResumeEditDemo } from '@/components/landing/resume-edit-demo';
import { Reveal } from '@/components/landing/reveal';
import { LiquidTexture } from '@/components/brand/liquid-texture';
import { Display, Eyebrow, Texture } from '@/components/brand/primitives';
import { SampleMatch } from '@/components/landing/sample-match';
import { SiteFooter } from '@/components/landing/site-footer';
import { SiteHeader } from '@/components/landing/site-header';
import { Steps } from '@/components/landing/steps';
import {
  applicationData,
  faqData,
  graph,
  organisationData,
  websiteData,
} from '@/components/landing/structured-data';
import { FEATURE_PAGES, featurePath, HOME_FAQS } from '@/content/marketing';
import { cn } from '@/lib/utils';

export const metadata: Metadata = { alternates: { canonical: '/' } };

const JOB_SITES = ['LinkedIn', 'Naukri', 'Indeed', 'Internshala', 'Company career pages'] as const;

const FRESH_COMPANIES = [
  'Google',
  'Microsoft',
  'Amazon',
  'Atlassian',
  'NVIDIA',
  'Freshworks',
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

const EDITOR_FACTS = [
  { title: 'Any line, any section', body: 'Change, remove or add. Enter adds a bullet.' },
  { title: 'Live preview', body: 'Your own PDF, redrawn as you type.' },
  { title: 'Links keep working', body: 'LinkedIn, GitHub and project links follow.' },
  { title: 'Asks, never invents', body: 'Claims you never gave wait for you.' },
] as const;

const STEPS = [
  {
    title: 'Upload your resume',
    body: 'We turn it into a profile and an evidence bank you can review and correct.',
  },
  {
    title: 'Find or check a job',
    body: "See this week's jobs picked for your experience, paste any link, or open a job page and read your score beside the Apply button.",
  },
  {
    title: 'Match your resume and apply',
    body: 'Tick the skills you really have, edit any line yourself or ask the AI, then let autofill fill the form. You review it and submit.',
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
  { label: 'Never', body: 'Adds a skill, number or link you never gave.' },
  { label: 'Never', body: 'Changes a job title, employer or date unless you ask.' },
  { label: 'Never', body: 'Overwrites what you typed into a form.' },
  { label: 'Not stored', body: 'An edited resume is kept only when you press Save.' },
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
          <LiquidTexture className="hero-drift -z-10 [mask-image:linear-gradient(to_bottom,transparent_50%,black_95%)] opacity-45" />

          <div className="mx-auto flex w-full max-w-6xl flex-col justify-center px-5 pt-12 pb-28 sm:pt-16 lg:min-h-[calc(100svh-4rem)] lg:py-12">
            <HeroJobCheck>
              <Eyebrow>Free job check · no sign-in</Eyebrow>
              <Display as="h1" className="mt-6 sm:text-6xl lg:text-[4.25rem]">
                Know your fit <span className="text-primary">before you apply</span>
              </Display>
              <p className="text-foreground/75 mx-auto mt-5 max-w-xl text-lg text-pretty lg:mx-0">
                Paste a job link. We read the page and list every skill it asks for. Add your resume
                to get an honest job match score, with the evidence behind each skill.
              </p>
            </HeroJobCheck>
          </div>
        </section>

        <div className={RAILS}>
          <section id="extension" className={cn(GUTTER, 'scroll-mt-16 py-20 sm:py-28')}>
            <ExtensionSection />
          </section>

          <section
            id="what"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <Reveal className="max-w-3xl">
              <Eyebrow>What Rolesetu is</Eyebrow>
              <Display className="mt-6">
                <span className="block">One assistant for</span>
                <span className="text-primary block">the whole job application.</span>
              </Display>
              <p className="text-muted-foreground mt-6 text-lg text-pretty">
                Rolesetu is a web app and browser extension for people applying to jobs. Upload your
                resume once. It finds this week&apos;s jobs that fit your experience, tells you how
                well you fit any job and why, lets you edit your resume yourself or by asking its
                AI, fills the application form, and keeps a record of what you applied to and what
                came back. It prepares the work; you decide what gets sent.
              </p>
            </Reveal>

            <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURE_PAGES.map((page, index) => (
                <Reveal as="li" key={page.slug} delay={(index % 3) * 80}>
                  <Link
                    href={featurePath(page.slug)}
                    className="group bg-card hover:border-foreground/30 focus-visible:ring-ring/60 flex h-full flex-col rounded-2xl border p-5 transition-[border-color,box-shadow,translate] duration-200 outline-none hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/5 focus-visible:ring-2 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                  >
                    <h3 className="flex items-center justify-between gap-3 font-medium">
                      {page.name}
                      <ArrowRight className="text-muted-foreground size-4 shrink-0 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
                    </h3>
                    <p className="text-muted-foreground mt-2 text-sm">{page.summary}</p>
                  </Link>
                </Reveal>
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

          <section
            id="fresh-jobs"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <div className="grid items-center gap-12 lg:grid-cols-[7fr_5fr] lg:gap-16">
              <Reveal className="lg:order-last">
                <Eyebrow>Fresh jobs · new</Eyebrow>
                <Display className="mt-6">
                  <span className="block">This week&apos;s jobs,</span>
                  <span className="text-primary block">picked for you.</span>
                </Display>
                <p className="text-muted-foreground mt-6 max-w-md text-lg">
                  Every morning we read top companies&apos; own careers sites and list the jobs in
                  India posted in the last 7 days. Only roles that fit your experience are shown,
                  each with your match score.
                </p>
                <div className="mt-6 flex flex-wrap gap-2 text-sm">
                  {FRESH_COMPANIES.map((company) => (
                    <span key={company} className="bg-muted rounded-full px-3 py-1 font-medium">
                      {company}
                    </span>
                  ))}
                  <span className="text-muted-foreground px-1 py-1">and 50 more</span>
                </div>
                <Link
                  href={featurePath('fresh-jobs')}
                  className="text-primary mt-4 inline-flex items-center gap-2 py-3 text-sm font-medium hover:underline"
                >
                  See how fresh jobs are picked
                  <ArrowRight className="size-4" />
                </Link>
              </Reveal>
              <Reveal
                delay={120}
                className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.47_0.15_45)] p-4 sm:p-8"
              >
                <LiquidTexture className="-z-10 opacity-20" />
                <FreshJobsDemo />
              </Reveal>
            </div>
          </section>

          <section className={cn(GUTTER, 'border-t border-dashed py-20 sm:py-28')}>
            <div className="grid items-center gap-12 lg:grid-cols-[5fr_7fr] lg:gap-16">
              <Reveal>
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
                  className="text-primary mt-4 inline-flex items-center gap-2 py-3 text-sm font-medium hover:underline"
                >
                  See how a job gets scored
                  <ArrowRight className="size-4" />
                </Link>
              </Reveal>
              <Reveal
                delay={120}
                className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.5_0.24_292)] p-4 sm:p-8"
              >
                <LiquidTexture className="-z-10 opacity-25" />
                <SampleMatch />
              </Reveal>
            </div>

            <dl className="mt-16 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {SCORE_FACTS.map((fact, index) => (
                <Reveal key={fact.title} delay={index * 80} className="border-t pt-4">
                  <dt className="text-sm font-medium">{fact.title}</dt>
                  <dd className="text-muted-foreground mt-1.5 text-sm">{fact.body}</dd>
                </Reveal>
              ))}
            </dl>
          </section>

          <section
            id="resume"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <div className="grid items-center gap-12 lg:grid-cols-[7fr_5fr] lg:gap-16">
              <Reveal className="lg:order-last">
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
                  className="text-primary mt-4 inline-flex items-center gap-2 py-3 text-sm font-medium hover:underline"
                >
                  See how resume tailoring works
                  <ArrowRight className="size-4" />
                </Link>
              </Reveal>
              <Reveal
                delay={120}
                className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.43_0.11_155)] p-4 sm:p-8"
              >
                <LiquidTexture className="-z-10 opacity-20" />
                <ResumeEditDemo />
              </Reveal>
            </div>

            <dl className="mt-16 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {RESUME_FACTS.map((fact, index) => (
                <Reveal key={fact.title} delay={index * 80} className="border-t pt-4">
                  <dt className="text-sm font-medium">{fact.title}</dt>
                  <dd className="text-muted-foreground mt-1.5 text-sm">{fact.body}</dd>
                </Reveal>
              ))}
            </dl>
          </section>

          <section
            id="editor"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <div className="grid items-center gap-12 lg:grid-cols-[5fr_7fr] lg:gap-16">
              <Reveal>
                <Eyebrow>Resume editor · new</Eyebrow>
                <Display className="mt-6">
                  <span className="block">Edit any line.</span>
                  <span className="text-primary block">Or just ask.</span>
                </Display>
                <p className="text-muted-foreground mt-6 max-w-md text-lg">
                  Change, remove or add anything on your resume and watch your own PDF redraw as you
                  type. Or tell the AI what you want, like &ldquo;add my Rolesetu project&rdquo;. It
                  works from your resume and profile, and asks when it does not know.
                </p>
                <Link
                  href={featurePath('resume-editor')}
                  className="text-primary mt-4 inline-flex items-center gap-2 py-3 text-sm font-medium hover:underline"
                >
                  See how the resume editor works
                  <ArrowRight className="size-4" />
                </Link>
              </Reveal>
              <Reveal
                delay={120}
                className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.42_0.13_205)] p-4 sm:p-8"
              >
                <LiquidTexture className="-z-10 opacity-20" />
                <ResumeAssistantDemo />
              </Reveal>
            </div>

            <dl className="mt-16 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {EDITOR_FACTS.map((fact, index) => (
                <Reveal key={fact.title} delay={index * 80} className="border-t pt-4">
                  <dt className="text-sm font-medium">{fact.title}</dt>
                  <dd className="text-muted-foreground mt-1.5 text-sm">{fact.body}</dd>
                </Reveal>
              ))}
            </dl>
          </section>

          <section
            id="features"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <Reveal className="mx-auto max-w-3xl text-center">
              <Eyebrow>One profile, every step</Eyebrow>
              <Display className="mt-6">
                <span className="block">From finding a job</span>
                <span className="text-primary block">to hearing back.</span>
              </Display>
              <p className="text-muted-foreground mx-auto mt-5 max-w-xl text-lg">
                Your resume is read once. After that every tool works from the same profile and the
                same evidence.
              </p>
            </Reveal>
            <Reveal delay={120} className="mt-14">
              <FeatureShowcase />
            </Reveal>
          </section>

          <section
            id="how-it-works"
            className={cn(GUTTER, 'scroll-mt-16 border-t border-dashed py-20 sm:py-28')}
          >
            <Steps steps={STEPS}>
              <Display>
                <span className="block">From resume to reply</span>
                <span className="text-primary block">in five steps.</span>
              </Display>
              <p className="text-muted-foreground mt-6 max-w-md text-lg">
                Set up once. After that, each job takes a few seconds to check and a few clicks to
                apply.
              </p>
            </Steps>
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
              {PROMISES.map((promise, index) => (
                <Reveal
                  as="li"
                  key={promise.body}
                  delay={(index % 3) * 70}
                  className="bg-background flex min-h-40 flex-col p-6"
                >
                  <p className="text-muted-foreground font-mono text-[0.6875rem] tracking-[0.14em] uppercase">
                    {promise.label}
                  </p>
                  <p className="mt-auto pt-8 text-lg leading-snug font-medium tracking-tight">
                    {promise.body}
                  </p>
                </Reveal>
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
            <Reveal>
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
            </Reveal>
          </section>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
