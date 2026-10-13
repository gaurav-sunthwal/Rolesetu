'use client';

import { useMutation } from '@tanstack/react-query';
import { ArrowRight, Link2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { z } from 'zod';

import {
  ErrorScoreCard,
  ExampleScoreCard,
  LoadingScoreCard,
  LockedScoreCard,
} from '@/components/landing/hero-score-card';
import { previewJob } from '@/features/preview/api';
import { errorMessage } from '@/lib/api/client';

// A real site name with a dot in it, so "react developer" is not sent off as a link.
const jobLink = z.url({ protocol: /^https?$/, hostname: /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i });

function withScheme(link: string): string {
  const trimmed = link.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

/**
 * The landing page's main action: read a real job from its link, before any
 * sign-in. The heading sits beside the result, so both fit one laptop screen.
 */
export function HeroJobCheck({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState('');
  const [invalid, setInvalid] = useState(false);
  const result = useRef<HTMLDivElement>(null);
  const preview = useMutation({ mutationFn: previewJob });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const url = withScheme(value);
    const valid = jobLink.safeParse(url).success;
    setInvalid(!valid);
    if (!valid) return;
    preview.mutate(url);
    // On a phone the result sits below the form, so bring it into view.
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    result.current?.scrollIntoView({ block: 'nearest', behavior: calm ? 'auto' : 'smooth' });
  }

  // The single phone column is told it may shrink; otherwise one long unbroken
  // line (a link, a web address) makes the whole hero wider than the screen.
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-14">
      <div className="animate-in fade-in slide-in-from-bottom-3 fill-mode-both text-center duration-700 motion-reduce:animate-none lg:text-left">
        {children}

        <form
          noValidate
          onSubmit={submit}
          className="bg-background focus-within:ring-ring/60 mx-auto mt-8 flex max-w-xl flex-col gap-2 rounded-2xl border p-2 shadow-lg shadow-black/5 transition-shadow focus-within:ring-2 sm:flex-row sm:items-center sm:pl-4 lg:mx-0"
        >
          <Link2 className="text-muted-foreground hidden size-5 shrink-0 sm:block" />
          <input
            type="url"
            inputMode="url"
            autoComplete="off"
            aria-label="Job link"
            aria-invalid={invalid}
            aria-describedby={invalid ? 'hero-link-error' : 'hero-link-hint'}
            placeholder="Paste a job link"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className="placeholder:text-muted-foreground h-12 w-full min-w-0 shrink-0 bg-transparent px-3 text-left text-base outline-none sm:w-auto sm:flex-1 sm:shrink sm:px-0"
          />
          <button
            type="submit"
            disabled={preview.isPending}
            className="group bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-ring/60 flex h-12 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-base font-medium shadow-sm transition-[background-color,scale] outline-none focus-visible:ring-2 active:scale-[0.98] disabled:opacity-60 motion-reduce:transition-none"
          >
            {preview.isPending ? 'Reading…' : 'Check this job'}
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
          </button>
        </form>

        {invalid ? (
          <p id="hero-link-error" role="alert" className="text-destructive mt-3 text-sm">
            That does not look like a job link. Paste the full address, like
            https://company.com/careers/job-title
          </p>
        ) : (
          <p id="hero-link-hint" className="text-foreground/70 mt-3 text-sm text-pretty">
            Free, no sign-in. Works with LinkedIn, Naukri, Indeed, Wellfound and company career
            pages.
          </p>
        )}
      </div>

      <div
        ref={result}
        className="animate-in fade-in slide-in-from-bottom-4 fill-mode-both mx-auto w-full max-w-xl scroll-mt-24 delay-150 duration-700 motion-reduce:animate-none lg:max-w-none"
      >
        {preview.isPending ? (
          <LoadingScoreCard />
        ) : preview.isError ? (
          <ErrorScoreCard message={errorMessage(preview.error)} url={preview.variables} />
        ) : preview.data ? (
          <LockedScoreCard job={preview.data} />
        ) : (
          <ExampleScoreCard />
        )}
      </div>
    </div>
  );
}
