import { ArrowRight, Puzzle } from 'lucide-react';
import Link from 'next/link';
import { z } from 'zod';

import { featurePath } from '@/content/marketing';

// Set once the Chrome Web Store has approved the extension; until then it is "coming soon".
const storeUrl = z
  .url()
  .optional()
  .parse(process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL || undefined);

const LINK =
  'text-primary inline-flex shrink-0 items-center gap-1.5 py-2 text-sm font-medium underline-offset-4 hover:underline';

/** A strip under the hero saying where the browser extension stands. */
export function ExtensionBanner() {
  return (
    <aside
      aria-label="Browser extension"
      className="bg-card mx-auto flex w-full max-w-6xl flex-col gap-x-6 gap-y-3 border-x border-b border-dashed px-5 py-5 sm:px-10 md:flex-row md:items-center lg:px-16"
    >
      <div className="flex items-center gap-3">
        <span className="bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg">
          <Puzzle className="size-4" />
        </span>
        <p className="font-medium">Chrome extension</p>
        <span className="bg-primary text-primary-foreground rounded-full px-2.5 py-0.5 font-mono text-[0.6875rem] tracking-wide uppercase">
          {storeUrl ? 'New' : 'Coming soon'}
        </span>
      </div>
      <p className="text-muted-foreground min-w-0 flex-1 text-sm text-pretty">
        Your match score beside the Apply button on LinkedIn, Naukri and Indeed, with autofill for
        the application form.
        {storeUrl ? '' : ' Until it is in the store, check any job by pasting its link above.'}
      </p>
      {storeUrl ? (
        <a href={storeUrl} target="_blank" rel="noreferrer" className={LINK}>
          Add to Chrome
          <ArrowRight className="size-3.5" />
        </a>
      ) : (
        <Link href={featurePath('job-search-extension')} className={LINK}>
          See what it will do
          <ArrowRight className="size-3.5" />
        </Link>
      )}
    </aside>
  );
}
