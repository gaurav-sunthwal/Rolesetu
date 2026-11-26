import { describe, expect, it } from 'vitest';

import { APPLY, SUBMIT } from '../lib/apply-controls';
import { APPLYING_WORDS } from '../lib/autofill/fields';
import { dialogTitle } from '../lib/job-detect';

describe('dialogTitle', () => {
  it('takes the job out of an "Applying to ... job" heading', () => {
    expect(dialogTitle('Applying to Full Stack Developer job')).toBe('Full Stack Developer');
    expect(dialogTitle('Applying for  Android App Development internship')).toBe(
      'Android App Development',
    );
  });

  it('leaves a plain title as it is', () => {
    expect(dialogTitle('  Full Stack   Developer ')).toBe('Full Stack Developer');
    expect(dialogTitle('React.js Developer - job post')).toBe('React.js Developer');
  });
});

describe('SUBMIT', () => {
  it('matches the buttons that send an application form', () => {
    for (const label of ['Submit', 'submit application', 'Send your application', 'Apply and submit']) {
      expect(SUBMIT.test(label)).toBe(true);
    }
  });

  it('does not match other buttons, nor the Apply ones', () => {
    for (const label of ['Submit feedback', 'Subscribe', 'Apply now']) {
      expect(SUBMIT.test(label)).toBe(false);
    }
    expect(APPLY.test('Submit')).toBe(false);
  });
});

describe('APPLYING_WORDS', () => {
  it('knows a Google Forms application on any of its pages', () => {
    for (const text of [
      'Which work setup are you applying for?',
      'Have your resume link, repository link and design links ready',
      'Link to your resume',
      'Full-Stack Engineer Intern (Frontend)',
      'Stipend: Rs 6,000 per month',
      'Apply now',
    ]) {
      expect(APPLYING_WORDS.test(text)).toBe(true);
    }
  });

  it('does not take a checkout or an internal tool for an application', () => {
    for (const text of ['Apply coupon', 'Internal notes', 'International shipping', 'Resume playback']) {
      expect(APPLYING_WORDS.test(text)).toBe(false);
    }
  });
});
