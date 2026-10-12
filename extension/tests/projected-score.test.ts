import { describe, expect, it } from 'vitest';

import { projectedScore } from '../lib/projected-score';

type Skill = { name: string; required: boolean; verdict: 'strong' | 'partial' | 'missing' };
const skill = (name: string, verdict: Skill['verdict'], required = true): Skill => ({
  name,
  required,
  verdict,
});
const match = (skills: Skill[], score: number, cap: number | null = null) =>
  ({ skill_results: skills, score, score_cap: cap }) as Parameters<typeof projectedScore>[0];

describe('projectedScore', () => {
  const skills = [skill('React', 'strong'), skill('GraphQL', 'missing'), skill('Docker', 'missing')];

  it('is the current score when nothing is ticked', () => {
    expect(projectedScore(match(skills, 33), [])).toEqual({ score: 33, heldBack: false });
  });

  it('rises as missing skills are ticked, and falls back when unticked', () => {
    expect(projectedScore(match(skills, 33), ['GraphQL']).score).toBe(67);
    expect(projectedScore(match(skills, 33), ['GraphQL', 'Docker']).score).toBe(100);
    expect(projectedScore(match(skills, 33), []).score).toBe(33);
  });

  it('counts an any-one-of requirement as met by one of its options', () => {
    const either = [skill('React', 'strong'), skill('GraphQL or gRPC', 'missing')];
    expect(projectedScore(match(either, 50), ['gRPC']).score).toBe(100);
    expect(projectedScore(match(either, 50), ['Kotlin']).score).toBe(50);
  });

  it('never promises more than experience allows, and says so', () => {
    const capped = projectedScore(match(skills, 33, 60), ['GraphQL', 'Docker']);
    expect(capped).toEqual({ score: 60, heldBack: false });
    // Already at the limit: ticking adds nothing, and the reason is experience.
    expect(projectedScore(match(skills, 60, 60), ['GraphQL', 'Docker'])).toEqual({
      score: 60,
      heldBack: true,
    });
  });

  it('ignores ticks for skills the job did not ask for', () => {
    expect(projectedScore(match(skills, 33), ['Kotlin']).score).toBe(33);
  });

  it('copes with a job that lists no skills', () => {
    expect(projectedScore(match([], 0), ['React'])).toEqual({ score: 0, heldBack: false });
  });
});
