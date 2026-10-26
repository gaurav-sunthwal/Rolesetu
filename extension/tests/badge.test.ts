import { describe, expect, it } from 'vitest';

import { badgeForMatch, NOT_CONNECTED_BADGE } from '../lib/badge';
import type { Match } from '../lib/messages';

const match = (fields: Partial<Match>): Match =>
  ({ status: 'completed', score: 72, error: null, ...fields }) as Match;

describe('badgeForMatch', () => {
  it('shows the rounded score for a scored job', () => {
    expect(badgeForMatch({ ok: true, data: match({ score: 71.6 }) }).text).toBe('72');
  });

  it('shows "!" when scoring failed on the server', () => {
    const badge = badgeForMatch({
      ok: true,
      data: match({ status: 'failed', score: null, error: 'No profile' }),
    });
    expect(badge.text).toBe('!');
    expect(badge.title).toContain('No profile');
  });

  it('shows "!" with the reason when the request failed', () => {
    const badge = badgeForMatch({
      ok: false,
      status: 500,
      message: 'Server down',
    });
    expect(badge.text).toBe('!');
    expect(badge.title).toContain('Server down');
  });

  it('asks to connect when the key was refused', () => {
    expect(badgeForMatch({ ok: false, status: 401, message: 'x' })).toEqual(NOT_CONNECTED_BADGE);
  });
});
