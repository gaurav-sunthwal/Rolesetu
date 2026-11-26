import { describe, expect, it } from 'vitest';

import { asksForWords } from '../lib/autofill/ai-fit';

const textarea = { multiLine: true, type: '' };
const input = { multiLine: false, type: 'text' };

describe('asksForWords', () => {
  it('offers AI on every multi-line question', () => {
    expect(asksForWords(textarea, 'Anything else you would like us to know?', 'question')).toBe(true);
    expect(asksForWords(textarea, 'Additional information', null)).toBe(true);
    expect(asksForWords(textarea, 'Describe your role', 'job_description')).toBe(true);
  });

  it('offers AI on single-line questions that ask for words, not only "Why..." ones', () => {
    for (const question of [
      'What is your biggest strength?',
      'Your favourite project and what you learned',
      'What do you know about our product?',
      'Why do you want to join us?',
      'Describe your notice period situation',
    ]) {
      expect(asksForWords(input, question, 'question')).toBe(true);
    }
  });

  it('offers AI on link questions: the profile has the links', () => {
    expect(asksForWords(input, 'Link to a repository of your work', 'question')).toBe(true);
    expect(asksForWords({ multiLine: false, type: 'url' }, 'Link to interfaces you have designed', 'question')).toBe(true);
  });

  it('never offers AI on facts only the user knows', () => {
    for (const question of [
      'Years of experience with React',
      'Current CTC (LPA)',
      'Expected joining date',
      'Current city',
      'Do you have a valid passport?',
      'Are you willing to work night shifts?',
    ]) {
      expect(asksForWords(input, question, 'question')).toBe(false);
    }
    expect(asksForWords(textarea, 'Notice period', 'notice_period')).toBe(false);
    expect(asksForWords({ multiLine: false, type: 'number' }, 'How much do you like us?', 'question')).toBe(false);
  });

  it('leaves profile fields to the profile', () => {
    expect(asksForWords(input, 'First name', 'first_name')).toBe(false);
    expect(asksForWords({ multiLine: false, type: 'email' }, 'Email', 'email')).toBe(false);
  });
});
