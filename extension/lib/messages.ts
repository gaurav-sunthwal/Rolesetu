import type { components } from '../../dashboard/src/lib/api/schema';

import type { TrackedEvent } from './analytics';
import type { ReviewAnswer } from './review-ask';

export type Match = components['schemas']['MatchRead'];
export type SkillResult = components['schemas']['SkillResult'];
export type AutofillData = components['schemas']['AutofillData'];
export type Tailored = components['schemas']['TailoredRead'];
export type TailorRequest = components['schemas']['TailorRequest'];
export type KeywordCheck = components['schemas']['KeywordCheck'];
export type LearnedAnswer = components['schemas']['LearnedAnswer'];
export type LearnedAnswerRead = components['schemas']['LearnedAnswerRead'];
export type QuestionToMatch = components['schemas']['QuestionToMatch'];
export type ReusedAnswer = components['schemas']['QuestionMatchRead'];
export type PitchAnswer = components['schemas']['PitchAnswerRead'];
export type PitchRequest = components['schemas']['PitchAnswersRequest'];
export type AiAnswerRequest = components['schemas']['AiAnswerRequest'];
export type AiAnswer = components['schemas']['AiAnswerRead'];
export type ActivityYear = components['schemas']['ActivityYear'];
export type ApplicationStats = components['schemas']['ApplicationStats'];
export type Credits = components['schemas']['CreditsRead'];

/** What the popup shows about the user's job hunt. A part the server could not give is null. */
export type Summary = {
  activity: ActivityYear | null;
  stats: ApplicationStats | null;
  credits: Credits | null;
};

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
  | { type: 'activate'; found?: 'job' | 'form'; frame?: 'top' }
  | { type: 'frame-job'; strict: boolean }
  | { type: 'autofill-data' }
  | { type: 'learn-answers'; answers: LearnedAnswer[] }
  | { type: 'forget-answer'; key: string }
  | { type: 'answer-matches'; questions: QuestionToMatch[] }
  | { type: 'pitch-answers'; request: PitchRequest }
  | { type: 'ai-answer'; request: AiAnswerRequest }
  | { type: 'keyword-check'; matchId: string }
  | { type: 'tailor-resume'; changes: TailorRequest }
  | { type: 'keep-resume'; changes: TailorRequest }
  | { type: 'check-job'; job: DetectedJob }
  | { type: 'record-application'; job: TrackedJob; status: 'saved' | 'applied' }
  | { type: 'pending-apply'; action: 'get' }
  | { type: 'pending-apply'; action: 'set'; value: PendingApply }
  | { type: 'pending-apply'; action: 'clear' }
  | { type: 'open-dashboard'; path: string }
  | { type: 'track-events'; events: TrackedEvent[] }
  /** `refresh: false` answers from the saved copy only; `true` fetches when it is due. */
  | { type: 'summary'; timezone: string; refresh: boolean }
  | { type: 'review-ask'; action: 'check' }
  | { type: 'review-ask'; action: 'shown' }
  | { type: 'review-ask'; action: 'answer'; answer: ReviewAnswer };

export type Failure = { ok: false; status: number | null; message: string };
export type Result<T> = { ok: true; data: T } | Failure;

export type Responses = {
  connection: Result<{ connected: boolean }>;
  activate: Result<null>;
  'frame-job': Result<DetectedJob | null>;
  'autofill-data': Result<AutofillData>;
  'learn-answers': Result<LearnedAnswerRead[]>;
  'forget-answer': Result<null>;
  'answer-matches': Result<ReusedAnswer[]>;
  'pitch-answers': Result<PitchAnswer[]>;
  'ai-answer': Result<AiAnswer>;
  'keyword-check': Result<KeywordCheck>;
  'tailor-resume': Result<Tailored>;
  'keep-resume': Result<{ filename: string; skills_added: string[] }>;
  'check-job': Result<Match>;
  'record-application': Result<{ id: string; status: string }>;
  'pending-apply': Result<PendingApply | null>;
  'open-dashboard': Result<null>;
  'track-events': Result<null>;
  /** null when nothing is saved yet (only with `refresh: false`). */
  summary: Result<{ summary: Summary; savedAt: number; due: boolean } | null>;
  /** Whether to ask for a review now, and how many applications Rolesetu helped with. */
  'review-ask': Result<{ ask: boolean; applications: number }>;
};

export async function ask<T extends Request>(request: T): Promise<Responses[T['type']]> {
  try {
    const reply = (await browser.runtime.sendMessage(request)) as Responses[T['type']] | undefined;
    // No reply at all means the background worker was not there to answer.
    if (reply && typeof reply === 'object' && 'ok' in reply) return reply;
    return {
      ok: false,
      status: null,
      message: 'Rolesetu did not answer. Reload this page and try again.',
    } as Responses[T['type']];
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
