import { z } from 'zod';

// The public address of the site. Canonical links, the sitemap and social
// previews are all built from it, so it must be the address people really use.
const url = z
  .url()
  .parse(process.env.NEXT_PUBLIC_SITE_URL || 'https://rolesetu.vercel.app')
  .replace(/\/$/, '');

export const SITE = {
  name: 'Rolesetu',
  url,
  title: 'Rolesetu: job match score, resume tailoring and application tracker',
  tagline: 'Know your fit before you apply',
  description:
    'Rolesetu scores any job description against your resume skill by skill, adds the job’s keywords to your own resume PDF, autofills application forms and tracks every application, including replies in Gmail.',
  keywords: [
    'job match score',
    'resume match score',
    'resume job description match',
    'resume checker for job description',
    'ATS resume keywords',
    'tailor resume to job description',
    'resume keyword checker',
    'autofill job applications',
    'job application tracker',
    'job application tracker Gmail',
    'job search Chrome extension',
    'LinkedIn job match score',
    'Naukri resume match',
    'Indeed job match',
    'skill gap analysis for jobs',
  ],
  // The day the public pages last changed. Bump it when their content does.
  updated: '2026-10-13',
} as const;

export function absoluteUrl(path: string): string {
  return `${SITE.url}${path === '/' ? '' : path}`;
}

// The same values under flat names, for files that import them one at a time.
export const SITE_URL = SITE.url;
export const SITE_NAME = SITE.name;
export const SITE_TITLE = SITE.title;
export const SITE_DESCRIPTION = SITE.description;
