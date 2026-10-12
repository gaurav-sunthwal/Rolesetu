import type { Match } from './messages';

const POINTS = {
  required: { strong: 2, partial: 1, missing: 0 },
  niceToHave: { strong: 1, partial: 0.5, missing: 0 },
} as const;

/** Rounds like the server does (halves go to the even number). */
function roundHalfEven(value: number): number {
  const floor = Math.floor(value);
  if (value - floor !== 0.5) return Math.round(value);
  return floor % 2 === 0 ? floor : floor + 1;
}

/**
 * What the score would be if the ticked skills were on the user's profile.
 * The same sum the server does (backend scoring.py, and the
 * same function in the dashboard): a skill the user lists
 * counts as fully shown. It is a preview: the server's own figure replaces it
 * once the resume is saved.
 */
export function projectedScore(
  match: Pick<Match, 'skill_results' | 'score' | 'score_cap'>,
  ticked: readonly string[],
): { score: number; heldBack: boolean } {
  let earned = 0;
  let possible = 0;
  for (const skill of match.skill_results) {
    const table = skill.required ? POINTS.required : POINTS.niceToHave;
    // "React or Angular or Vue" is one requirement: ticking any one of them meets it.
    const met = skill.name.split(' or ').some((option) => ticked.includes(option));
    earned += table[met ? 'strong' : skill.verdict];
    possible += table.strong;
  }
  const fromSkills = possible === 0 ? 0 : roundHalfEven((earned / possible) * 100);
  const cap = match.score_cap ?? null;
  const current = match.score ?? 0;
  const score = Math.max(cap === null ? fromSkills : Math.min(fromSkills, cap), current);
  // "Held back" is when ticking added nothing because experience is the limit.
  return { score, heldBack: cap !== null && fromSkills > cap && score === current };
}
