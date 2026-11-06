import { describe, expect, it } from 'vitest';

import { isPrivateQuestion } from '../lib/autofill/learn';

describe('isPrivateQuestion', () => {
  it.each([
    'Aadhaar number',
    'PAN card',
    'Bank account number',
    'Password',
    'Confirm password',
    'Race / Ethnicity',
    'Do you have a disability?',
    'Veteran status',
    'Religion',
    'Have you ever been convicted of a crime?',
    'Marital status',
  ])('never keeps "%s"', (question) => {
    expect(isPrivateQuestion(question)).toBe(true);
  });

  it.each(['Notice period', 'Expected CTC', 'How did you hear about us?', 'Postal code', 'PIN code'])(
    'keeps "%s"',
    (question) => {
      expect(isPrivateQuestion(question)).toBe(false);
    },
  );
});
