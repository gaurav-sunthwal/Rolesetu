'use client';

import { Suspense } from 'react';

import { PreviewsList } from '@/components/lists/PreviewsList';
import { PageHeader, pill } from '@/components/ui';
import { useUrlFilter } from '@/lib/url-filter';

const SHOW = [
  { value: null, label: 'Everything' },
  { value: 'failed', label: 'Could not read' },
  { value: 'paid', label: 'Paid reader' },
] as const;

function Previews() {
  const [show, setShow] = useUrlFilter('show');
  const [host, setHost] = useUrlFilter('host');

  return (
    <>
      <PageHeader
        title="Landing previews"
        subtitle="Job links visitors pasted on the landing page in the last 24 hours, newest first. Kept for a day."
      />
      <div className="mb-6 flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
        {SHOW.map((option) => (
          <button
            key={option.label}
            onClick={() => setShow(option.value)}
            aria-pressed={show === option.value}
            className={pill(show === option.value)}
          >
            {option.label}
          </button>
        ))}
        {host && (
          <button onClick={() => setHost(null)} className={pill(true)} title="Show every site">
            Site: {host} <span aria-hidden>×</span>
            <span className="sr-only">(remove)</span>
          </button>
        )}
      </div>
      <PreviewsList hours={24} host={host} paid={show === 'paid'} failed={show === 'failed'} />
    </>
  );
}

export default function PreviewsPage() {
  return (
    <Suspense>
      <Previews />
    </Suspense>
  );
}
