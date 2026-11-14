import { describe, expect, it } from 'vitest';

import { browserName, plain } from '../lib/browser-name';

describe('what an install says about its browser', () => {
  it('names the browser, not the engine or the placeholder brand', () => {
    const brands = [
      { brand: 'Not_A Brand', version: '99' },
      { brand: 'Chromium', version: '142' },
      { brand: 'Google Chrome', version: '142' },
    ];
    expect(browserName(brands, '')).toBe('Google Chrome 142');
  });

  it('falls back to Chromium, then to Firefox from the user agent', () => {
    expect(browserName([{ brand: 'Chromium', version: '142' }], '')).toBe('Chromium 142');
    expect(browserName(undefined, 'Mozilla/5.0 (X11; Linux) Gecko/20100101 Firefox/133.0')).toBe('Firefox 133');
    expect(browserName([], 'Something else')).toBeUndefined();
  });

  it('keeps only plain characters, within the length the server accepts', () => {
    expect(plain('<b>en-GB</b>', 20)).toBe('ben-GB/b');
    expect(plain('x'.repeat(30), 20)).toHaveLength(20);
    expect(plain('   ', 20)).toBeUndefined();
    expect(plain('Europe/Bucharest', 50, /[^\w/+-]/g)).toBe('Europe/Bucharest');
  });
});
