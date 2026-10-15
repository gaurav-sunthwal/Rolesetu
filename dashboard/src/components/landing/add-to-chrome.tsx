import { ArrowUpRight } from 'lucide-react';

import { SITE } from '@/lib/site';
import { cn } from '@/lib/utils';

/** Opens the extension's Chrome Web Store page, where it is installed. */
export function AddToChrome({ className }: { className?: string }) {
  return (
    <a
      href={SITE.chromeExtensionUrl}
      target="_blank"
      rel="noreferrer"
      className={cn(
        'bg-foreground text-background hover:bg-foreground/90 inline-flex h-12 items-center gap-2 rounded-xl px-6 text-base font-medium',
        className,
      )}
    >
      Add to Chrome
      <ArrowUpRight className="size-4" aria-hidden />
      <span className="sr-only">(opens the Chrome Web Store)</span>
    </a>
  );
}
