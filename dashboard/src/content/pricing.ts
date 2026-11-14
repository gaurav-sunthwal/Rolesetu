/**
 * What each plan includes, shown on the landing page and the dashboard's Plan page.
 * The numbers match the backend (`modules/credits`, `modules/billing/plans.py`,
 * `modules/referrals`); change them together.
 */

export const PRICE = { pro: 199, referral: 149, currency: '₹' } as const;
export const CREDITS = { free: 30, pro: 400 } as const;
export const CHECKS_TO_UNLOCK = 3;

export type PlanCell = boolean | string;

export interface PlanRow {
  feature: string;
  detail?: string;
  free: PlanCell;
  pro: PlanCell;
}

export const PLAN_ROWS: PlanRow[] = [
  {
    feature: 'AI credits every month',
    detail: 'One AI answer or resume-assistant message uses one credit.',
    free: `${CREDITS.free}`,
    pro: `${CREDITS.pro}`,
  },
  {
    feature: 'AI answers on application forms',
    detail: '“Why this company?”, written from your profile and checked against it.',
    free: `Up to ${CREDITS.free} a month`,
    pro: `Up to ${CREDITS.pro} a month`,
  },
  {
    feature: 'Resume assistant',
    detail: 'Ask for changes in plain words; every claim checked against your resume.',
    free: `Up to ${CREDITS.free} messages`,
    pro: `Up to ${CREDITS.pro} messages`,
  },
  { feature: 'Job match score, skills and gaps', free: 'Unlimited', pro: 'Unlimited' },
  { feature: 'Browser extension: score badge and autofill', free: true, pro: true },
  { feature: 'Tailored resume PDF and resume editor', free: true, pro: true },
  { feature: 'Fresh jobs from company career pages', free: true, pro: true },
  { feature: 'Application tracker with Gmail updates', free: true, pro: true },
];

export const FREE_POINTS = [
  'Unlimited job checks with the match score',
  'Extension autofill on job sites',
  'Tailored resume PDFs and the editor',
  `${CREDITS.free} AI credits a month`,
];

export const PRO_POINTS = [
  `${CREDITS.pro} AI credits a month, over 13× Free`,
  'AI answers on every application form',
  'Much more resume-assistant help',
  'Everything in Free, still unlimited',
];

export const REFERRAL_STEPS = [
  {
    title: 'Share your invite link',
    body: 'Find it on your Plan page. Send it on WhatsApp, LinkedIn, anywhere.',
  },
  {
    title: 'Your friend starts using Rolesetu',
    body: `They sign up with your link, upload a resume and check ${CHECKS_TO_UNLOCK} jobs.`,
  },
  {
    title: `Your next month is ${PRICE.currency}${PRICE.referral}`,
    body: `Instead of ${PRICE.currency}${PRICE.pro}. Every friend unlocks one cheaper month, so keep sharing.`,
  },
] as const;
