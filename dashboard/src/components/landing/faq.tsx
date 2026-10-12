import { Plus } from 'lucide-react';

import type { Faq } from '@/content/marketing';

/**
 * Questions that open in place. Built on <details>, so every answer is in the
 * page for search engines and works without JavaScript.
 */
export function FaqList({ faqs }: { faqs: readonly Faq[] }) {
  return (
    <div className="border-t">
      {faqs.map((faq) => (
        <details key={faq.question} className="group border-b">
          <summary className="focus-visible:ring-ring/60 flex cursor-pointer list-none items-start justify-between gap-6 rounded-sm py-5 text-left outline-none focus-visible:ring-2 [&::-webkit-details-marker]:hidden">
            <h3 className="text-lg font-medium tracking-tight">{faq.question}</h3>
            <Plus
              aria-hidden
              className="text-muted-foreground mt-1 size-5 shrink-0 transition-transform group-open:rotate-45 motion-reduce:transition-none"
            />
          </summary>
          <p className="text-muted-foreground max-w-2xl pb-6 text-pretty">{faq.answer}</p>
        </details>
      ))}
    </div>
  );
}
