import { describe, expect, it } from 'vitest';

import { asTemplate, fillTokens, nameVariants, templateParts } from '../lib/autofill/fill';

const UNISOUK = { company: 'UniSouk', role: 'Full Stack Developer' };
const FINFLOCK = { company: 'Finflock', role: 'AI Engineer' };

describe('written answers reused for another company', () => {
  it("swaps this job's names for tokens and the next job's names back in", () => {
    const typed = 'I want to join UniSouk as a Full Stack Developer because unisouk builds for real sellers.';
    const template = asTemplate(typed, UNISOUK);
    expect(template).toBe('I want to join {company} as a {role} because {company} builds for real sellers.');
    expect(fillTokens(template, FINFLOCK)).toBe(
      'I want to join Finflock as an AI Engineer because Finflock builds for real sellers.',
    );
  });

  it('leaves short answers and partial words alone', () => {
    expect(asTemplate('Yes, UniSouk', UNISOUK)).toBe('Yes, UniSouk');
    expect(asTemplate('I worked at UniSoukLabs on payments and growth for a year.', UNISOUK)).toBe(
      'I worked at UniSoukLabs on payments and growth for a year.',
    );
  });

  it('reads as a sentence when the page gave no names', () => {
    expect(fillTokens('I would love to join {company} in the {role} role.', { company: null, role: null })).toBe(
      'I would love to join your company in the open role.',
    );
  });
});

describe('the company name in a saved answer', () => {
  const LOOPR =
    "I'm very interested in Loopr AI because my experience aligns well with the kind of work you do." +
    " My full-stack background would allow me to contribute across the stack at Loopr AI.";

  it('becomes {company} in every place, and the next company goes back in', () => {
    const { text, swapped } = templateParts(LOOPR, { company: 'Loopr AI', role: null });
    expect(swapped).toEqual(['Loopr AI']);
    expect(text).not.toContain('Loopr');
    expect(fillTokens(text, { company: 'Encord', role: null })).toBe(
      "I'm very interested in Encord because my experience aligns well with the kind of work you do." +
        ' My full-stack background would allow me to contribute across the stack at Encord.',
    );
  });

  it('is found however the answer writes it', () => {
    expect(nameVariants('Finflock Systems Private Limited')).toEqual([
      'Finflock Systems Private Limited',
      'Finflock Systems',
      'Finflock',
    ]);
    expect(nameVariants('Loopr AI')).toEqual(['Loopr AI', 'Loopr']);
    // Too common to mean the company on its own.
    expect(nameVariants('Data Axle')).toEqual(['Data Axle']);
    const { text } = templateParts('I would love to build at Loopr, the team behind Loopr AI tools.', {
      company: 'Loopr AI',
      role: null,
    });
    expect(text).toBe('I would love to build at {company}, the team behind {company} tools.');
  });

  it('reports nothing swapped when the page did not give the name', () => {
    expect(templateParts(LOOPR, { company: null, role: null }).swapped).toEqual([]);
  });
});
