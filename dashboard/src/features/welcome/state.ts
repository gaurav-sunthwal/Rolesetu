import type { Profile } from '@/lib/api/types';

/** Nothing on the profile yet: no name, headline, skills, roles, projects or education. */
export function isProfileEmpty(profile: Profile): boolean {
  return (
    !profile.full_name &&
    !profile.headline &&
    profile.skills.length + profile.experience.length === 0 &&
    profile.projects.length + profile.education.length === 0
  );
}

// Remembered per account in this browser, so someone who skipped the setup is
// not sent back to it. Losing it (private window, cleared data) only means the
// setup is offered once more.
const key = (uid: string) => `rolesetu:welcome-done:${uid}`;

export function isWelcomeDone(uid: string): boolean {
  try {
    return window.localStorage.getItem(key(uid)) === '1';
  } catch {
    return false;
  }
}

export function markWelcomeDone(uid: string): void {
  try {
    window.localStorage.setItem(key(uid), '1');
  } catch {
    // Storage blocked: the setup may be offered again, which is harmless.
  }
}

/** Pages a new user is sent to the setup from: where sign-in and the extension land. */
export const WELCOME_FROM = new Set(['/app', '/app/settings']);
