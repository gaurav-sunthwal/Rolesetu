import type { DetectedJob } from './messages';

// Lines shorter than this are labels and buttons ("Save", "2 days ago"), which
// change on their own and say nothing about which job is on screen.
const MIN_LINE = 40;
const SHARED = 0.6;

function plain(value: string | null): string {
  return (value ?? '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function linesOf(description: string): Set<string> {
  return new Set(
    description
      .split('\n')
      .map(plain)
      .filter((line) => line.length >= MIN_LINE),
  );
}

/**
 * Whether two readings of the page show the same job.
 *
 * The readings are never identical: a description arrives in pieces, and the
 * text around it keeps changing ("Save" becomes "Saved", the applicant count
 * goes up). So the title and company must match, and most of the shorter
 * description's sentences must be in the longer one. Anything stricter starts
 * the score over, and discards an updated resume, for a job that did not change.
 */
export function sameJob(first: DetectedJob | null, second: DetectedJob | null): boolean {
  if (first === null || second === null) return first === second;
  if (plain(first.title) !== plain(second.title)) return false;
  if (plain(first.company) !== plain(second.company)) return false;

  const before = linesOf(first.description);
  const after = linesOf(second.description);
  if (before.size === 0 || after.size === 0) {
    return plain(first.description) === plain(second.description);
  }
  let shared = 0;
  for (const line of before) if (after.has(line)) shared += 1;
  return shared / Math.min(before.size, after.size) >= SHARED;
}
