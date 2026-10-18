import { z } from 'zod';

const KEY = 'rolesetu.career-companies';

/** "All" stays all as companies are added; otherwise the chosen slugs. */
export type CompanyPicks = { all: true } | { all: false; slugs: string[] };

const picksSchema = z.union([
  z.object({ all: z.literal(true) }),
  z.object({ all: z.literal(false), slugs: z.array(z.string()) }),
]);

export const ALL_COMPANIES: CompanyPicks = { all: true };

/**
 * The companies a user follows, kept in this browser for the beta (they move
 * to the user's account with the database step). Storage can be refused, so
 * every call tolerates that and falls back to all companies.
 */
export function readPicks(): CompanyPicks {
  try {
    if (typeof window === 'undefined') return ALL_COMPANIES;
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return ALL_COMPANIES;
    const parsed = picksSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : ALL_COMPANIES;
  } catch {
    return ALL_COMPANIES;
  }
}

export function savePicks(picks: CompanyPicks): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(picks));
  } catch {
    // The choice still applies until the page is reloaded.
  }
}
