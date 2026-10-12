import type { components } from '../../dashboard/src/lib/api/schema';

export type Match = components['schemas']['MatchRead'];
export type SkillResult = components['schemas']['SkillResult'];
export type AutofillData = components['schemas']['AutofillData'];
export type Tailored = components['schemas']['TailoredRead'];
export type TailorRequest = components['schemas']['TailorRequest'];
export type KeywordCheck = components['schemas']['KeywordCheck'];

export type DetectedJob = {
  title: string | null;
  company: string | null;
  description: string;
  url: string;
};

/** Enough about a scored job to put it in the application tracker. */
export type TrackedJob = { matchId: string; role: string; company: string; url: string };

/**
 * An application the user has started but we have not seen finish. Kept by the
 * background worker, because applying often moves through several pages.
 */
export type PendingApply = TrackedJob & { startedAt: number };

/** Requests a page or the popup can make of the background worker. */
export type Request =
  | { type: 'connection' }
  | { type: 'activate' }
  | { type: 'autofill-data' }
  | { type: 'keyword-check'; matchId: string }
  | { type: 'tailor-resume'; changes: TailorRequest }
  | { type: 'keep-resume'; changes: TailorRequest }
  | { type: 'check-job'; job: DetectedJob }
  | { type: 'record-application'; job: TrackedJob; status: 'saved' | 'applied' }
  | { type: 'pending-apply'; action: 'get' }
  | { type: 'pending-apply'; action: 'set'; value: PendingApply }
  | { type: 'pending-apply'; action: 'clear' }
  | { type: 'open-dashboard'; path: string };

export type Failure = { ok: false; status: number | null; message: string };
export type Result<T> = { ok: true; data: T } | Failure;

export type Responses = {
  connection: Result<{ connected: boolean }>;
  activate: Result<null>;
  'autofill-data': Result<AutofillData>;
  'keyword-check': Result<KeywordCheck>;
  'tailor-resume': Result<Tailored>;
  'keep-resume': Result<{ filename: string; skills_added: string[] }>;
  'check-job': Result<Match>;
  'record-application': Result<{ id: string; status: string }>;
  'pending-apply': Result<PendingApply | null>;
  'open-dashboard': Result<null>;
};

export async function ask<T extends Request>(request: T): Promise<Responses[T['type']]> {
  try {
    return (await browser.runtime.sendMessage(request)) as Responses[T['type']];
  } catch {
    return {
      ok: false,
      status: null,
      message: 'Rolesetu was updated. Reload this page and try again.',
    } as Responses[T['type']];
  }
}

/** Messages between the dashboard page and the extension, over window.postMessage. */
export const PAGE_SOURCE = 'rolesetu-dashboard';
export const EXTENSION_SOURCE = 'rolesetu-extension';
