import { describe, expect, it } from 'vitest';
import { fullerThan } from '../lib/job-detect';

const job = (description: string) => ({ title: null, company: null, description });

// What sits around the Apply button on an Oracle careers page: no requirements.
const AROUND_BUTTON = job(
  'About Us\nHoneywell is a global automation company.\nApply now\nJob Info\nJob Schedule Full time',
);
const WHOLE_JOB = job(
  'Key Responsibilities\nParticipate in code reviews.\nYou must have\nBasic understanding of software development.\n' +
    'Requirements\nExperience with programming languages such as Java, Python, or C++.\nAbout Us\n' +
    'Honeywell is a global automation company.\nApply now\nJob Info\nJob Schedule Full time',
);

describe('fullerThan', () => {
  it('uses the whole job when the block by the Apply button holds only part of it', () => {
    expect(fullerThan(AROUND_BUTTON, WHOLE_JOB)).toBe(WHOLE_JOB);
  });

  it('keeps a block that already reads like a whole job', () => {
    const list = job(`${WHOLE_JOB.description}\n${WHOLE_JOB.description}\nMore jobs`);
    expect(fullerThan(WHOLE_JOB, list)).toBe(WHOLE_JOB);
  });

  it('falls back to the page when there is no block by the button', () => {
    expect(fullerThan(null, WHOLE_JOB)).toBe(WHOLE_JOB);
    expect(fullerThan(AROUND_BUTTON, null)).toBe(AROUND_BUTTON);
  });
});
