'use client';

import { useEffect, useRef } from 'react';

import { cn } from '@/lib/utils';

/**
 * Fades its content up into place the first time it scrolls into view.
 *
 * The hidden state is applied by script, only to content still below the
 * screen, so the page reads in full without JavaScript and nothing already
 * visible flickers. The motion itself lives in globals.css and is skipped for
 * people who ask for reduced motion.
 */
export function Reveal({
  as = 'div',
  delay = 0,
  className,
  children,
}: {
  as?: 'div' | 'li' | 'section';
  /** Milliseconds to wait, so a row of items arrives one after another. */
  delay?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (element.getBoundingClientRect().top < window.innerHeight * 0.9) return;

    element.dataset.reveal = 'pending';
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        element.dataset.reveal = 'shown';
        observer.disconnect();
      },
      { rootMargin: '0px 0px -10% 0px' },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // One element type for the compiler; at run time it is whichever tag was asked for.
  const Tag = as as 'div';
  return (
    <Tag
      ref={ref}
      data-reveal=""
      style={{ '--reveal-delay': `${delay}ms` } as React.CSSProperties}
      className={cn('group/reveal', className)}
    >
      {children}
    </Tag>
  );
}
