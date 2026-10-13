import { ArrowRight, Check } from 'lucide-react';
import { z } from 'zod';

import { Display, Eyebrow } from '@/components/brand/primitives';
import { ExtensionWaitlist } from '@/components/landing/extension-waitlist';
import { Reveal } from '@/components/landing/reveal';
import { VideoPlayer } from '@/components/landing/video-player';

// Set once the Chrome Web Store has approved the extension; until then people join a waiting list.
const storeUrl = z
  .url()
  .optional()
  .parse(process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL || undefined);

const VIDEO = {
  id: '8BgRPZmmg9w',
  title: 'Rolesetu: check your resume against a job on Naukri, LinkedIn and Indeed',
};

const POINTS = [
  'Your match score beside the Apply button, on the job page itself.',
  'Works on LinkedIn, Naukri, Indeed and company career pages.',
  'Fills the application form from your profile. You review and submit.',
] as const;

/** The browser extension: what it does, a video of it, and how to get it (or hear when you can). */
export function ExtensionSection() {
  return (
    <div className="grid items-center gap-12 lg:grid-cols-[5fr_7fr] lg:gap-16">
      <Reveal>
        <Eyebrow>{storeUrl ? 'Chrome extension · new' : 'Chrome extension · coming soon'}</Eyebrow>
        <Display className="mt-6">
          <span className="block">Your score, right</span>
          <span className="text-primary block">on the job page.</span>
        </Display>
        <p className="text-muted-foreground mt-6 max-w-md text-lg">
          {storeUrl
            ? 'No more copying links. Open a job and Rolesetu scores it against your resume where you are already looking.'
            : 'No more copying links. Open a job and Rolesetu scores it against your resume where you are already looking. Watch it work, then get an email the day it is ready.'}
        </p>
        <ul className="mt-6 space-y-2.5">
          {POINTS.map((point) => (
            <li key={point} className="flex items-start gap-2.5 text-sm">
              <Check className="text-primary mt-0.5 size-4 shrink-0" />
              {point}
            </li>
          ))}
        </ul>
        <div className="mt-8 max-w-md">
          {storeUrl ? (
            <a
              href={storeUrl}
              target="_blank"
              rel="noreferrer"
              className="bg-foreground text-background hover:bg-foreground/90 inline-flex h-12 items-center gap-2 rounded-xl px-6 text-base font-medium"
            >
              Add to Chrome
              <ArrowRight className="size-4" />
            </a>
          ) : (
            <ExtensionWaitlist />
          )}
        </div>
      </Reveal>
      <Reveal delay={120}>
        <VideoPlayer videoId={VIDEO.id} title={VIDEO.title} />
      </Reveal>
    </div>
  );
}
