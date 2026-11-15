import { describe, expect, it } from 'vitest';

import { namesThisPage } from '../lib/job-detect';

describe('namesThisPage', () => {
  it('trusts job data whose title is the page heading or opens the tab title', () => {
    // Kula (slice's job board): the heading by the Apply button is "Life at slice:".
    expect(namesThisPage('SDE 2 - Data Platform', 'SDE 2 - Data Platform', '')).toBe(true);
    expect(
      namesThisPage('SDE 2 - Data Platform', '', 'SDE 2 - Data Platform – Bengaluru | slice Careers'),
    ).toBe(true);
    expect(namesThisPage('  sde 2 -  data platform ', 'SDE 2 - Data Platform', '')).toBe(true);
  });

  it('does not trust data left over from another listing', () => {
    expect(namesThisPage('Backend Engineer', 'Frontend Engineer', 'Jobs | LinkedIn')).toBe(false);
    expect(namesThisPage('QA', 'Engineering jobs', 'QA Lead | Acme')).toBe(false);
    expect(namesThisPage('', '', '')).toBe(false);
  });
});
