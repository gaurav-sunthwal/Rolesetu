import { describe, expect, it } from 'vitest';

import { fitJob, fitUrl, messageFor, MIN_DESCRIPTION } from '../lib/api-errors';

describe('messageFor', () => {
  it('shows what the server wrote for people', () => {
    expect(messageFor(422, { detail: 'A skill name is too long (the limit is 60).' })).toBe(
      'A skill name is too long (the limit is 60).',
    );
  });

  it('shows the first reason from a field-by-field list', () => {
    const body = { detail: [{ msg: 'Value error, Choose at least one change to make.' }] };
    expect(messageFor(422, body)).toBe('Choose at least one change to make.');
  });

  it('never falls back to a message that says nothing', () => {
    // Replies with no usable body: an error page, an empty body, something odd.
    for (const body of [null, undefined, '', 'Internal Server Error', {}, { detail: 42 }, []]) {
      for (const status of [400, 403, 404, 413, 422, 429, 500, 502, 503]) {
        const message = messageFor(status, body);
        expect(message.length).toBeGreaterThan(20);
        expect(message).not.toMatch(/could not complete that/i);
      }
    }
  });

  it('says whose side a server failure is on', () => {
    expect(messageFor(500, null)).toMatch(/on its side, not yours/);
    expect(messageFor(503, 'Service Unavailable')).toMatch(/on its side, not yours/);
    expect(messageFor(429, null)).toMatch(/Wait a minute/);
  });
});

describe('fitJob', () => {
  const description = 'Requirements: React and TypeScript. '.repeat(10);
  const job = { title: 'React Developer', company: 'Acme', description, url: 'https://x.test/j/1' };

  it('passes an ordinary job through unchanged', () => {
    expect(fitJob(job)).toEqual({
      jd_text: description.trim(),
      url: 'https://x.test/j/1',
      role: 'React Developer',
      company: 'Acme',
    });
  });

  it('cuts a title, company and description that are longer than the server accepts', () => {
    const fitted = fitJob({
      ...job,
      title: 'Senior '.repeat(60),
      company: 'Very Long Company Name '.repeat(20),
      description: 'x'.repeat(50000),
    });
    if ('problem' in fitted) throw new Error(fitted.problem);
    expect(fitted.role?.length).toBeLessThanOrEqual(160);
    expect(fitted.company?.length).toBeLessThanOrEqual(160);
    expect(fitted.jd_text.length).toBe(20000);
  });

  it('explains instead of sending a description too short to score', () => {
    const fitted = fitJob({ ...job, description: 'Apply now!' });
    expect(fitted).toHaveProperty('problem');
    expect(fitJob({ ...job, description: 'x'.repeat(MIN_DESCRIPTION) })).not.toHaveProperty(
      'problem',
    );
  });

  it('treats an empty title or company as unknown', () => {
    expect(fitJob({ ...job, title: '   ', company: null })).toMatchObject({
      role: null,
      company: null,
    });
  });
});

describe('fitUrl', () => {
  it('drops a tracking tail that makes the address too long, or the address itself', () => {
    const tail = `?trk=${'a'.repeat(3000)}`;
    expect(fitUrl(`https://jobs.test/view/42${tail}`)).toBe('https://jobs.test/view/42');
    expect(fitUrl(`https://jobs.test/${'a'.repeat(3000)}`)).toBeNull();
    expect(fitUrl('https://jobs.test/view/42?id=7')).toBe('https://jobs.test/view/42?id=7');
  });
});
