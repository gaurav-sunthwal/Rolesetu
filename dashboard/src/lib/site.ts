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
  // Where the extension is installed from. NEXT_PUBLIC_CHROME_EXTENSION_URL can point elsewhere.
  chromeExtensionUrl: z
    .url()
    .parse(
      process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL ||
        'https://chromewebstore.google.com/detail/bbpdnhlpapbkiadfdnkhacamojlkfbjl',
    ),
  // Published on the privacy policy and the Chrome Web Store listing.
  contactEmail: 'gauravsunthwalwork@gmail.com',
  description:
    'Paste a job link to see the skills it asks for, free. Rolesetu scores it against your resume, tailors your resume PDF, autofills forms and tracks applications.',
  keywords: [
    'Rolesetu',
    'job match score',
    'free job description checker',
    'job description skills checker',
    'check job fit before applying',
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
  updated: '2026-10-16',
} as const;

export function absoluteUrl(path: string): string {
  return `${SITE.url}${path === '/' ? '' : path}`;
}

// The same values under flat names, for files that import them one at a time.
export const SITE_URL = SITE.url;
export const SITE_NAME = SITE.name;
export const SITE_TITLE = SITE.title;
export const SITE_DESCRIPTION = SITE.description;
