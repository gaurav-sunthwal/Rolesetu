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

describe('isPrivateQuestion', () => {
  it('keeps away from payment and identity fields', () => {
    for (const words of ['Credit card number', 'Card number', 'CVV', 'Bank account number', 'IFSC', 'PAN', 'SWIFT code', 'Password']) {
      expect(isPrivateQuestion(words)).toBe(true);
    }
  });

  it('does not mistake ordinary questions or site field names for private ones', () => {
    for (const words of [
      'What has been your favorite project or proudest accomplishment? Why? cards[ac978161-6f46][field0]',
      'Years of experience with Swift',
      'Have you built a scorecard or dashboard?',
      'Experience in banking domain',
    ]) {
      expect(isPrivateQuestion(words)).toBe(false);
    }
  });
});
