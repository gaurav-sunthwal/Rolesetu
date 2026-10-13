'use client';

import { useEffect, useRef, useState } from 'react';

import { cn } from '@/lib/utils';

type Step = { title: string; body: string };

/**
 * The numbered steps beside a heading that stays put. The step crossing the
 * middle of the screen is lit, and a row of bars under the heading shows how
 * far through the list the reader is.
 */
export function Steps({ steps, children }: { steps: readonly Step[]; children: React.ReactNode }) {
  const [active, setActive] = useState(0);
  const items = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(items.current.indexOf(entry.target as HTMLLIElement));
        }
      },
      // A thin band across the middle of the screen: one step is in it at a time.
      { rootMargin: '-45% 0px -45% 0px' },
    );
    for (const item of items.current) if (item) observer.observe(item);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
      <div className="lg:sticky lg:top-28 lg:self-start">
        {children}
        <div aria-hidden className="mt-8 hidden max-w-xs items-center gap-1.5 lg:flex">
          {steps.map((step, index) => (
            <span
              key={step.title}
              className={cn(
                'h-1 flex-1 rounded-full transition-colors duration-500 motion-reduce:transition-none',
                index <= active ? 'bg-primary' : 'bg-muted',
              )}
            />
          ))}
          <span className="text-muted-foreground ml-2 font-mono text-xs tabular-nums">
            0{active + 1} / 0{steps.length}
          </span>
        </div>
      </div>
      <ol>
        {steps.map((step, index) => (
          <li
            key={step.title}
            ref={(element) => {
              items.current[index] = element;
            }}
            className="border-b py-8 first:pt-0 last:border-b-0"
          >
            <p
              className={cn(
                'font-mono text-4xl tracking-tight transition-colors duration-500 motion-reduce:transition-none',
                index === active ? 'text-primary' : 'text-muted-foreground/50',
              )}
            >
              0{index + 1}
            </p>
            <h3 className="mt-5 text-xl font-medium tracking-tight">{step.title}</h3>
            <p className="text-muted-foreground mt-2 max-w-md">{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
