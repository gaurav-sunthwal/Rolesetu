/** What each place an error can come from means, in plain words. */
export const SOURCES: Record<string, { label: string; help: string }> = {
  api: { label: 'API', help: 'The server failed while handling a request' },
  'job-check': { label: 'Job checks', help: 'Scoring a job failed in the background' },
  'job-link': { label: 'Job links', help: 'A job page could not be read' },
};

export const sourceLabel = (source: string) => SOURCES[source]?.label ?? source;

export const PERIODS = [
  { hours: 1, label: '1 hour' },
  { hours: 24, label: '24 hours' },
  { hours: 168, label: '7 days' },
  { hours: 720, label: '30 days' },
] as const;
