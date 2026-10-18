import { describe, expect, it } from 'vitest';

import { birthDateText, parseBirthDate } from '../lib/autofill/dates';

describe('parseBirthDate', () => {
  it('reads the value of a date picker', () => {
    expect(parseBirthDate('1998-05-12', '', 'en-IN')).toBe('1998-05-12');
  });

  it('follows the format the form shows', () => {
    expect(parseBirthDate('05/12/1998', 'MM/DD/YYYY', 'en-IN')).toBe('1998-05-12');
    expect(parseBirthDate('12/05/1998', 'DD/MM/YYYY', 'en-US')).toBe('1998-05-12');
  });

  it('falls back to the order this browser writes dates in', () => {
    expect(parseBirthDate('05/12/1998', 'date of birth', 'en-US')).toBe('1998-05-12');
    expect(parseBirthDate('12-05-1998', 'date of birth', 'en-GB')).toBe('1998-05-12');
  });

  it('lets a day above 12 settle the order', () => {
    expect(parseBirthDate('25/05/1998', 'MM/DD/YYYY', 'en-US')).toBe('1998-05-25');
    expect(parseBirthDate('05/25/1998', 'DD/MM/YYYY', 'en-GB')).toBe('1998-05-25');
  });

  it('reads a named month', () => {
    expect(parseBirthDate('12 May 1998', '', 'en-US')).toBe('1998-05-12');
    expect(parseBirthDate('May 12, 1998', '', 'en-GB')).toBe('1998-05-12');
  });

  it('ignores anything that is not a whole, real birth date', () => {
    expect(parseBirthDate('1998', '', 'en-IN')).toBeNull();
    expect(parseBirthDate('12/05', '', 'en-IN')).toBeNull();
    expect(parseBirthDate('31/02/1998', 'DD/MM/YYYY', 'en-IN')).toBeNull();
    expect(parseBirthDate('12/05/98', '', 'en-IN')).toBeNull();
    expect(parseBirthDate('12/05/2999', '', 'en-IN')).toBeNull();
  });
});

describe('birthDateText', () => {
  it('writes the date the way the field asks', () => {
    expect(birthDateText('1998-05-12', '', 'en-IN', 'date')).toBe('1998-05-12');
    expect(birthDateText('1998-05-12', 'DD/MM/YYYY', 'en-US', 'text')).toBe('12/05/1998');
    expect(birthDateText('1998-05-12', 'mm-dd-yyyy', 'en-IN', 'text')).toBe('05-12-1998');
    expect(birthDateText('1998-05-12', 'YYYY.MM.DD', 'en-IN', 'text')).toBe('1998.05.12');
    expect(birthDateText('1998-05-12', 'DD / MM / YYYY', 'en-IN', 'text')).toBe('12/05/1998');
  });

  it('uses the browser order when the form does not show one', () => {
    expect(birthDateText('1998-05-12', 'date of birth', 'en-US', 'text')).toBe('05/12/1998');
    expect(birthDateText('1998-05-12', 'date of birth', 'en-IN', 'text')).toBe('12/05/1998');
  });

  it('does not read words as a format', () => {
    expect(birthDateText('1998-05-12', 'comments dd', 'en-IN', 'text')).toBe('12/05/1998');
  });

  it('leaves an answer that is not a saved date alone', () => {
    expect(birthDateText('12th May', '', 'en-IN', 'text')).toBeNull();
  });
});
