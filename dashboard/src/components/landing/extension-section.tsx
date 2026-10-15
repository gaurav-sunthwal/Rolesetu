import { Check } from 'lucide-react';

import { Display, Eyebrow } from '@/components/brand/primitives';
import { AddToChrome } from '@/components/landing/add-to-chrome';
import { Reveal } from '@/components/landing/reveal';
import { VideoPlayer } from '@/components/landing/video-player';

const VIDEO = {
  id: '8BgRPZmmg9w',
  title: 'Rolesetu: check your resume against a job on Naukri, LinkedIn and Indeed',
};

const POINTS = [
  'Your match score beside the Apply button, on the job page itself.',
  'Works on LinkedIn, Naukri, Indeed and company career pages.',
  'Fills the application form from your profile. You review and submit.',
] as const;

/** The browser extension: what it does, a video of it, and where to get it. */
export function ExtensionSection() {
  return (
    <div className="grid items-center gap-12 lg:grid-cols-[5fr_7fr] lg:gap-16">
      <Reveal>
        <Eyebrow>Chrome extension · new</Eyebrow>
        <Display className="mt-6">
          <span className="block">Your score, right</span>
          <span className="text-primary block">on the job page.</span>
        </Display>
        <p className="text-muted-foreground mt-6 max-w-md text-lg">
          No more copying links. Open a job and Rolesetu scores it against your resume where you are
          already looking. Free on the Chrome Web Store.
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
          <AddToChrome />
          <p className="text-muted-foreground mt-3 text-sm">
            Also works in Edge, Brave and other Chromium browsers.
          </p>
        </div>
      </Reveal>
      <Reveal delay={120}>
        <VideoPlayer videoId={VIDEO.id} title={VIDEO.title} />
      </Reveal>
    </div>
  );
}
