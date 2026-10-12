import { describe, expect, it } from 'vitest';

import type { DetectedJob } from '../lib/messages';
import { sameJob } from '../lib/same-job';

const DUTIES =
  'Build and maintain user interfaces with React and TypeScript for millions of users.';
const NEEDS = 'Three or more years of experience with JavaScript, React, HTML and CSS.';
const TEAM = 'We are looking for someone who cares about accessibility and clear code.';

function job(description: string, over: Partial<DetectedJob> = {}): DetectedJob {
  return {
    title: 'Frontend Developer',
    company: 'Globex',
    description,
    url: 'https://jobs.example/1',
    ...over,
  };
}

describe('sameJob', () => {
  it('treats no job and no job as the same, and a job appearing as a change', () => {
    expect(sameJob(null, null)).toBe(true);
    expect(sameJob(null, job(DUTIES))).toBe(false);
    expect(sameJob(job(DUTIES), null)).toBe(false);
  });

  it('is not fooled by short text changing around the description', () => {
    const before = job(['Apply now', 'Save', '12 applicants', DUTIES, NEEDS, TEAM].join('\n'));
    const after = job(['Apply now', 'Saved', '13 applicants', DUTIES, NEEDS, TEAM].join('\n'));
    expect(sameJob(before, after)).toBe(true);
  });

  it('is the same job when the rest of the description loads later', () => {
    expect(sameJob(job(DUTIES), job([DUTIES, NEEDS, TEAM].join('\n')))).toBe(true);
  });

  it('sees a different title or company as a different job', () => {
    const text = [DUTIES, NEEDS, TEAM].join('\n');
    expect(sameJob(job(text), job(text, { title: 'Backend Developer' }))).toBe(false);
    expect(sameJob(job(text), job(text, { company: 'Initech' }))).toBe(false);
  });

  it('sees a different description under the same title and company as a different job', () => {
    const other = [
      'Design and run data pipelines in Python and Airflow for the analytics team.',
      'Five or more years of experience with SQL, Spark and cloud data warehouses.',
      TEAM,
    ].join('\n');
    expect(sameJob(job([DUTIES, NEEDS, TEAM].join('\n')), job(other))).toBe(false);
  });
});
