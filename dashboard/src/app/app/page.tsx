import { ArrowRight } from 'lucide-react';
import Link from 'next/link';

import { Texture } from '@/components/brand/primitives';
import { Greeting } from '@/components/layout/greeting';
import { Button } from '@/components/ui/button';
import {
  NumbersGrid,
  RecentApplicationsList,
  SetupSteps,
} from '@/features/overview/components/overview-live';

// Gated by client-side auth (see AuthGuard), so this page cannot be an instant navigation.
export const instant = false;

export default function OverviewPage() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
      <Greeting />

      <section className="relative isolate overflow-hidden rounded-2xl bg-[oklch(0.42_0.22_268)] p-8 text-white sm:p-12">
        <Texture className="-z-10 [mask-image:linear-gradient(to_right,transparent_25%,black)] opacity-35" />
        <div className="max-w-lg">
          <h3 className="text-3xl leading-[1.1] font-medium tracking-[-0.035em] text-balance sm:text-4xl">
            Found a job you like? See how you fit in seconds.
          </h3>
          <p className="mt-4 text-base text-white/80">
            Paste the link or the description. You get a score, the evidence behind it, and the gaps
            to close.
          </p>
          <Button
            nativeButton={false}
            render={<Link href="/app/check" />}
            size="lg"
            className="mt-7 bg-white text-black hover:bg-white/90"
          >
            Check a job
            <ArrowRight />
          </Button>
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-5">
        <SetupSteps />
        <NumbersGrid />
      </div>

      <RecentApplicationsList />
    </div>
  );
}
