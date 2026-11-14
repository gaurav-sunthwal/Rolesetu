import { describe, expect, it } from 'vitest';

import { keyForQuestion } from '../lib/autofill/fields';

// The server reads a question's words back out of its key to match rewordings
// (`phrasings` in saved_answers/matching.py), so the format must not drift.
describe('keyForQuestion', () => {
  it.each([
    ['Do you have a laptop with a stable internet connection?', 'q_do_you_have_a_laptop_with_a_stable_internet_connection'],
    ['Notice period *', 'q_notice_period'],
    ['Why should we hire you? (max 500 words)', 'q_why_should_we_hire_you_max_500_words'],
    ['currentLocation', 'q_current_location'],
  ])('stores "%s" as %s', (question, key) => {
    expect(keyForQuestion(question)).toBe(key);
  });

  it('keeps keys within what the server accepts', () => {
    const key = keyForQuestion('Please describe in detail the most challenging project you have ever worked on');
    expect(key).toMatch(/^[a-z0-9_]{1,60}$/);
  });
});
