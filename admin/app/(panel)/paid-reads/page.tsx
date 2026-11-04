'use client';

import { JobChecksList } from '@/components/lists/JobChecksList';
import { PreviewsList } from '@/components/lists/PreviewsList';
import { PageHeader } from '@/components/ui';

/** The paid page reader (Context.dev) is used in two places, so both are listed. */
export default function PaidReadsPage() {
  return (
    <>
      <PageHeader
        title="Paid page reads"
        subtitle="Job pages read through the paid reader (Context.dev credits) in the last 24 hours."
      />
      <div className="space-y-8">
        <section aria-labelledby="by-users">
          <h2 id="by-users" className="mb-3 font-bold">
            By signed-in users, in job checks
          </h2>
          <JobChecksList hours={24} paid />
        </section>
        <section aria-labelledby="by-visitors">
          <h2 id="by-visitors" className="mb-3 font-bold">
            By visitors, on the landing page
          </h2>
          <PreviewsList hours={24} paid />
        </section>
      </div>
    </>
  );
}
