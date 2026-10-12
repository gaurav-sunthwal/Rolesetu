'use client';

import { useEffect, useState } from 'react';

/**
 * Shown while the resume is being updated. The server does this in one step
 * and reports nothing along the way, so the bar is an estimate from how long
 * the work usually takes: quick at first, slowing down, and never reaching the
 * end until the result is really in.
 */
export function UpdateProgress() {
  const [percent, setPercent] = useState(5);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => {
      const seconds = (Date.now() - started) / 1000;
      setPercent(Math.min(95, Math.round(5 + 90 * (1 - Math.exp(-seconds / 2.2)))));
    }, 150);
    return () => clearInterval(timer);
  }, []);
  const step =
    percent < 35
      ? 'Reading your resume'
      : percent < 65
        ? 'Making your changes'
        : percent < 88
          ? 'Checking a job site can still read it'
          : 'Preparing the preview';

  return (
    <div className="bg-secondary rounded-2xl px-4 py-3" aria-live="polite">
      <p className="text-sm font-semibold">Updating your resume</p>
      <div
        role="progressbar"
        aria-label="Updating your resume"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="bg-border mt-2 h-2 overflow-hidden rounded-full"
      >
        <div
          className="bg-primary h-full rounded-full transition-[width] duration-200 ease-linear motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-muted-foreground mt-2 text-xs">
        {step}… {percent}%
      </p>
    </div>
  );
}
