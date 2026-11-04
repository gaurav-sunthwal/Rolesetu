'use client';

import { Suspense } from 'react';

import { JobChecksList } from '@/components/lists/JobChecksList';
import { PageHeader, pill } from '@/components/ui';
import { formatDate } from '@/lib/format';
import { useSetUrlFilters, useUrlFilter } from '@/lib/url-filter';

const PERIODS = [
  { hours: null, label: 'All time' },
  { hours: 24, label: '24 hours' },
  { hours: 168, label: '7 days' },
  { hours: 720, label: '30 days' },
] as const;

function JobChecks() {
  const [hoursParam] = useUrlFilter('hours');
  const [paidParam, setPaid] = useUrlFilter('paid');
  // Set by the Activity page, to list one day's checks.
  const [day, setDay] = useUrlFilter('day');
  const setFilters = useSetUrlFilters();
  const hours = hoursParam ? Number(hoursParam) : null;
  const paid = paidParam === '1';

  return (
    <>
      <PageHeader
        title="Job checks"
        subtitle="Every job any user has checked against their profile, newest first."
      />
      <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Filters">
        {PERIODS.map((period) => (
          <button
            key={period.label}
            onClick={() =>
              setFilters({ day: null, hours: period.hours ? String(period.hours) : null })
            }
            aria-pressed={!day && hours === period.hours}
            className={pill(!day && hours === period.hours)}
          >
            {period.label}
          </button>
        ))}
        <button
          onClick={() => setPaid(paid ? null : '1')}
          aria-pressed={paid}
          className={pill(paid)}
        >
          Paid reads only
        </button>
        {day && (
          <button onClick={() => setDay(null)} className={pill(true)} title="Show every day">
            {formatDate(day)} <span aria-hidden>×</span>
            <span className="sr-only">(remove)</span>
          </button>
        )}
      </div>
      <JobChecksList hours={hours} day={day} paid={paid} />
    </>
  );
}

export default function JobChecksPage() {
  return (
    <Suspense>
      <JobChecks />
    </Suspense>
  );
}
