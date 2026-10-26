import { cn } from '@/lib/utils';

// Sample jobs, worded the way the Fresh jobs page words them.
const JOBS = [
  {
    role: 'Software Engineer II',
    company: 'Atlassian',
    place: 'Bengaluru',
    posted: 'Posted 1 day ago',
    fit: 'fits',
    score: 82,
  },
  {
    role: 'Frontend Engineer',
    company: 'Freshworks',
    place: 'Chennai',
    posted: 'Posted 2 days ago',
    fit: 'fits',
    score: 74,
  },
  {
    role: 'Senior Software Engineer',
    company: 'Microsoft',
    place: 'Hyderabad',
    posted: 'Posted 3 days ago',
    fit: 'stretch',
    score: 61,
  },
] as const;

const FIT = {
  fits: {
    label: 'Fits your experience',
    className: 'bg-[oklch(0.94_0.06_155)] text-[oklch(0.4_0.12_155)]',
  },
  stretch: {
    label: 'Stretch: +1 year',
    className: 'bg-[oklch(0.95_0.07_80)] text-[oklch(0.42_0.1_70)]',
  },
} as const;

/** A few fresh jobs as the page shows them: newest first, judged on experience, then scored. */
export function FreshJobsDemo() {
  return (
    <div className="w-full text-left">
      <div className="flex items-center justify-between gap-3 text-white">
        <p className="text-sm font-medium">Fresh jobs · last 7 days</p>
        <span className="font-mono text-[0.6875rem] tracking-wide text-white/80 uppercase">
          Sample
        </span>
      </div>
      <ul className="mt-4 space-y-3">
        {JOBS.map((job) => (
          <li
            key={job.role}
            className="flex items-start gap-4 rounded-xl bg-white p-4 text-neutral-900 shadow-xl shadow-black/20"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{job.role}</span>
              <span className="block truncate text-sm text-neutral-600">
                {job.company} · {job.place}
              </span>
              <span className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span
                  className={cn('rounded-full px-2 py-0.5 font-medium', FIT[job.fit].className)}
                >
                  {FIT[job.fit].label}
                </span>
                <span className="text-neutral-500">{job.posted}</span>
              </span>
            </span>
            <span className="flex flex-col items-end">
              <span className="text-lg leading-none font-bold tabular-nums">{job.score}</span>
              <span className="mt-1 font-mono text-[0.625rem] text-neutral-500 uppercase">
                match
              </span>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-white/75">
        Read every morning from each company&apos;s own careers site. Jobs that ask for much more
        experience than you have are not shown.
      </p>
    </div>
  );
}
