import { describe, expect, it } from 'vitest';

import { newEvent } from '../lib/analytics';

describe('usage events', () => {
  it('carry their own id and time, so a retried batch is stored once', () => {
    const first = newEvent('autofill_filled', { count: 7, props: { drafts: 2 } });
    const second = newEvent('autofill_filled', { count: 7, props: { drafts: 2 } });
    expect(first.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(first.id).not.toBe(second.id);
    expect(Date.parse(first.at)).not.toBeNaN();
    expect(first).toMatchObject({ name: 'autofill_filled', count: 7, props: { drafts: 2 } });
  });

  it('keep numbers in the range the server accepts', () => {
    expect(newEvent('job_scored', { count: -3 }).count).toBe(0);
    expect(newEvent('job_scored', { count: 2.6 }).count).toBe(3);
    expect(newEvent('job_scored', { count: 10 ** 9 }).count).toBe(100_000);
  });

  it('name a site only when given one outside a web page', () => {
    expect(newEvent('form_detected').host).toBeUndefined();
    expect(newEvent('form_detected', {}, 'wellfound.com').host).toBe('wellfound.com');
    expect(newEvent('form_detected', { host: 'x.com' }, 'wellfound.com').host).toBe('x.com');
  });
});
