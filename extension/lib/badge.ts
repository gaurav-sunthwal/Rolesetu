import type { Match, Result } from '@/lib/messages';

/** What the toolbar icon shows. An empty text hides the badge. */
export type Badge = { text: string; color: string; title: string };

const SCORE_COLOR = '#2f5fe0';
const ERROR_COLOR = '#d64545';

export const NO_BADGE: Badge = {
  text: '',
  color: SCORE_COLOR,
  title: 'Rolesetu',
};

export const NOT_CONNECTED_BADGE: Badge = {
  text: '!',
  color: ERROR_COLOR,
  title: 'Rolesetu is not set up yet. Click to connect your account.',
};

/** The badge for a tab after its job was checked: the score, or "!" when it failed. */
export function badgeForMatch(result: Result<Match>): Badge {
  if (!result.ok) {
    if (result.status === 401) return NOT_CONNECTED_BADGE;
    return {
      text: '!',
      color: ERROR_COLOR,
      title: `Rolesetu: ${result.message}`,
    };
  }
  const match = result.data;
  if (match.status === 'failed' || match.score === null) {
    const reason = match.error ?? 'This job could not be scored.';
    return { text: '!', color: ERROR_COLOR, title: `Rolesetu: ${reason}` };
  }
  const score = Math.round(match.score);
  return {
    text: String(score),
    color: SCORE_COLOR,
    title: `Rolesetu: ${score}% match`,
  };
}
