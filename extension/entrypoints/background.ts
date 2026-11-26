import { fitJob, fitUrl, type JobRequest, messageFor, UNREACHABLE } from '@/lib/api-errors';
import { type Badge, badgeForMatch, NO_BADGE, NOT_CONNECTED_BADGE } from '@/lib/badge';
import { API_BASE_URL, DASHBOARD_URL, SETUP_PATH } from '@/lib/config';
import type {
  ActivityYear,
  ApplicationStats,
  AutofillData,
  Credits,
  DetectedJob,
  Failure,
  JobPreview,
  KeywordCheck,
  LearnedAnswerRead,
  Match,
  AiAnswer,
  PitchAnswer,
  ReusedAnswer,
  Request,
  Result,
  Summary,
  Tailored,
  TrackedJob,
} from '@/lib/messages';
import {
  AUTOFILL_FOR_MS,
  cached,
  digest,
  forget,
  JOB_FOR_MS,
  KEYWORDS_FOR_MS,
} from '@/lib/response-cache';
import { record, enqueue, flush as flushAnalytics, startAnalytics } from '@/lib/analytics-queue';
import { watchErrors } from '@/lib/analytics';
import { pendingApply } from '@/lib/session-storage';
import { installInfo, ownInstallId } from '@/lib/install';
import {
  applications,
  countEvents,
  FRESH_REVIEW_STATE as FRESH,
  markAnswered,
  markAsked,
  type ReviewState,
  shouldAsk,
} from '@/lib/review-ask';
import { accessKey, analyticsOff, reviewState, savedSummary } from '@/lib/storage';
import { needsRefresh } from '@/lib/summary-cache';

const NOT_CONNECTED: Failure = {
  ok: false,
  status: 401,
  message: 'Connect Rolesetu to your account to see your match score.',
};

// First try at once, then again after a short and a longer pause.
const RETRY_AFTER_MS = [0, 1500, 4000];
// What a host answers while the server behind it is still coming up.
const STARTING_UP = new Set([502, 503, 504]);
// A host's "not up yet" replies that mean the request never reached the server, so a
// call that must not run twice (it spends an AI credit) is still safe to send again.
// Not 504: the server may have done the work after the host stopped waiting.
const NEVER_ARRIVED = new Set([502, 503]);
// A call that runs a model may wait on a server waking up and then on the model itself.
const ONCE_TIMEOUT_MS = 90_000;

/** Calls the API as the connected user. Never throws: failures come back as data. */
/**
 * `once`: for a request that must not be sent twice (an AI answer is paid for and
 * counted each time). It waits longer and is never retried after a timeout.
 */
async function api<T>(path: string, init: RequestInit = {}, once = false): Promise<Result<T>> {
  const key = await accessKey.getValue();
  if (!key) return NOT_CONNECTED;

  // The server can be asleep or mid-restart, and then the first call fails or
  // gets a "starting up" reply. Waiting briefly and trying again is usually all
  // it takes. Every call here is safe to repeat: reads, a job check (the server
  // reuses the result), tracker writes (which carry a retry key) and saving
  // learned answers (saving the same answer twice changes nothing).
  let response: Response | null = null;
  for (const wait of RETRY_AFTER_MS) {
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    try {
      response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${key}`,
          ...init.headers,
        },
        signal: AbortSignal.timeout(once ? ONCE_TIMEOUT_MS : 25_000),
      });
    } catch {
      response = null;
      // A call sent once may have been done by the server before the connection dropped.
      if (once) break;
      continue;
    }
    if (!(once ? NEVER_ARRIVED : STARTING_UP).has(response.status)) break;
  }
  if (response === null) {
    return { ok: false, status: null, message: UNREACHABLE };
  }

  if (response.status === 401) {
    // The key was revoked from the dashboard: forget it, so the UI asks to reconnect.
    await accessKey.setValue(null);
    return NOT_CONNECTED;
  }
  if (response.status === 204) return { ok: true, data: null as T };
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    return { ok: false, status: response.status, message: messageFor(response.status, body) };
  }
  if (body === null) {
    // A success with nothing readable in it: treat it as the server's fault.
    return { ok: false, status: response.status, message: messageFor(502, null) };
  }
  return { ok: true, data: body as T };
}

/**
 * What a job asks for, before the browser is connected: no account, no key. The
 * page's own text is sent, so the server reads the skills from it without
 * fetching the link (which sign-in walls often block).
 */
async function previewJob(job: DetectedJob): Promise<Result<JobPreview>> {
  const fitted = fitJob(job);
  if ('problem' in fitted) return { ok: false, status: 422, message: fitted.problem };
  if (fitted.url === null) return { ok: false, status: 422, message: messageFor(422, null) };
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/public/job-previews`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: fitted.url,
        description: fitted.jd_text,
        title: fitted.role,
        company: fitted.company,
      }),
      signal: AbortSignal.timeout(25_000),
    });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok || body === null) {
      return { ok: false, status: response.status, message: messageFor(response.status, body) };
    }
    return { ok: true, data: body as JobPreview };
  } catch {
    return { ok: false, status: null, message: UNREACHABLE };
  }
}

type Application = { id: string; status: string };

/**
 * Puts a job in the tracker, or moves one already there forward. The match id
 * is the retry key, so the same job is never recorded twice. A status the user
 * has already moved past (interview, offer...) is never pulled back.
 */
async function recordApplication(
  job: TrackedJob,
  status: 'saved' | 'applied',
): Promise<Result<Application>> {
  const created = await api<Application>('/applications', {
    method: 'POST',
    headers: { 'Idempotency-Key': `ext-${job.matchId}` },
    body: JSON.stringify({
      role: job.role,
      company: job.company,
      url: fitUrl(job.url),
      status,
      match_id: job.matchId,
      source: 'extension',
    }),
  });
  if (!created.ok || status !== 'applied' || created.data.status !== 'saved') return created;

  // It was saved earlier (on the Apply click); now it is confirmed as applied.
  return api<Application>(`/applications/${created.data.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'applied', source: 'extension' }),
  });
}

// Asked again soon at first, when most model reads finish, then less often.
const POLL_AFTER_MS = [800, 1200, 1500, 2000];
const POLL_FOR_MS = 90_000;

/**
 * Scores a job. Most come back scored at once; a job the server hands to the
 * model (one outside tech, or one it reads from the link) comes back pending,
 * so this waits for it here and the page only ever sees a finished result.
 */
async function checkJob(job: JobRequest): Promise<Result<Match>> {
  const started = await api<Match>('/matches', {
    method: 'POST',
    // "Answer at once, I will poll": without it the server holds the request
    // until the result is ready, for older versions that could not poll.
    headers: { Prefer: 'respond-async' },
    body: JSON.stringify(job),
  });
  if (!started.ok || started.data.status !== 'pending') return settle(started);

  const deadline = Date.now() + POLL_FOR_MS;
  for (let attempt = 0; Date.now() < deadline; attempt += 1) {
    const wait = POLL_AFTER_MS[Math.min(attempt, POLL_AFTER_MS.length - 1)];
    await new Promise((resolve) => setTimeout(resolve, wait));
    const current = await api<Match>(`/matches/${started.data.id}`);
    if (!current.ok || current.data.status !== 'pending') return settle(current);
  }
  return {
    ok: false,
    status: null,
    message: 'Reading this job is taking longer than usual. Try again in a minute.',
  };
}

/** A check that finished but failed is shown as the failure it is, with its reason. */
function settle(result: Result<Match>): Result<Match> {
  if (result.ok && result.data.status === 'failed') {
    return {
      ok: false,
      status: 422,
      message: result.data.error ?? 'This job could not be scored. Try again.',
    };
  }
  return result;
}

/** A page's hostname without "www.", for analytics. Never the path. */
function hostOf(url: string | undefined): string | undefined {
  try {
    return url ? new URL(url).hostname.replace(/^www\./, '') || undefined : undefined;
  } catch {
    return undefined;
  }
}

/** Loads the score and autofill UI into the frame whose detector found something. */
function isDetectedJob(value: unknown): value is DetectedJob {
  if (typeof value !== 'object' || value === null) return false;
  const job = value as Record<string, unknown>;
  return (
    typeof job.description === 'string' &&
    job.description.length > 0 &&
    typeof job.url === 'string' &&
    (job.title === null || typeof job.title === 'string') &&
    (job.company === null || typeof job.company === 'string')
  );
}

async function activate(
  sender: Browser.runtime.MessageSender,
  frame?: 'top',
): Promise<Result<null>> {
  const tabId = sender.tab?.id;
  if (tabId === undefined) return { ok: false, status: null, message: 'No page to show this on.' };
  try {
    await browser.scripting.executeScript({
      // A job inside an embedded job board is shown on the page around it: a
      // frame is often as tall as its content, so a panel pinned inside it could
      // sit far below the screen. The panel reads the job from the frame.
      target: { tabId, frameIds: [frame === 'top' ? 0 : (sender.frameId ?? 0)] },
      files: ['/content-scripts/job.js'],
    });
    return { ok: true, data: null };
  } catch {
    return { ok: false, status: null, message: 'Rolesetu cannot run on this page.' };
  }
}

async function handle(request: Request, sender: Browser.runtime.MessageSender): Promise<unknown> {
  switch (request.type) {
    case 'activate': {
      const activated = await activate(sender, request.frame);
      if (activated.ok && request.found) record(`${request.found}_detected`, {}, hostOf(sender.tab?.url));
      return activated;
    }

    case 'frame-job': {
      // Asks the frames of the sender's tab (embedded job boards) for a job. Only
      // a frame that finds one answers; with none, nothing comes back.
      const tabId = sender.tab?.id;
      if (tabId === undefined) return { ok: true, data: null };
      try {
        const found: unknown = await browser.tabs.sendMessage(tabId, {
          type: 'read-job',
          strict: request.strict,
        });
        return { ok: true, data: isDetectedJob(found) ? found : null };
      } catch {
        return { ok: true, data: null };
      }
    }

    case 'autofill-data':
      return cached('autofill', AUTOFILL_FOR_MS, () => api<AutofillData>('/extension/autofill'));

    case 'learn-answers': {
      const learned = await api<LearnedAnswerRead[]>('/extension/learned-answers', {
        method: 'POST',
        body: JSON.stringify({ answers: request.answers }),
      });
      // The saved answers changed, so the next form must not get the old ones.
      if (learned.ok) await forget('autofill');
      return learned;
    }

    case 'forget-answer': {
      const forgotten = await api<null>(
        `/extension/learned-answers/${encodeURIComponent(request.key)}`,
        { method: 'DELETE' },
      );
      if (forgotten.ok) await forget('autofill');
      return forgotten;
    }

    case 'answer-matches':
      return api<ReusedAnswer[]>('/extension/answer-matches', {
        method: 'POST',
        body: JSON.stringify({ questions: request.questions }),
      });

    case 'ai-answer': {
      const answered = await api<AiAnswer>(
        '/extension/ai-answers',
        { method: 'POST', body: JSON.stringify(request.request) },
        true,
      );
      // AI answers spend credits, which the popup shows.
      if (answered.ok) await markSummaryStale();
      return answered;
    }

    case 'pitch-answers':
      return api<PitchAnswer[]>('/extension/pitch-answers', {
        method: 'POST',
        body: JSON.stringify(request.request),
      });

    case 'keyword-check':
      // Reading the resume PDF is the slowest part of opening a job: once per job result.
      // (The server waits for a job check that is still being saved, so no retry here.)
      return cached(`keywords:${request.matchId}`, KEYWORDS_FOR_MS, () =>
        api<KeywordCheck>(
          `/tailored-resumes/keywords?match_id=${encodeURIComponent(request.matchId)}`,
        ),
      );

    case 'tailor-resume':
      return api<Tailored>('/tailored-resumes', {
        method: 'POST',
        body: JSON.stringify(request.changes),
      });

    case 'keep-resume': {
      // The choices are sent, not a file: the server repeats the edit on the saved resume.
      const kept = await api('/tailored-resumes/keep', {
        method: 'POST',
        body: JSON.stringify(request.changes),
      });
      // New skills on the profile change every score and the resume itself.
      if (kept.ok) await Promise.all([forget('job:'), forget('keywords:')]);
      return kept;
    }

    case 'connection':
      return { ok: true, data: { connected: (await accessKey.getValue()) !== null } };

    case 'check-job': {
      const job = fitJob(request.job);
      const result: Result<Match> =
        'problem' in job
          ? { ok: false, status: 422, message: job.problem }
          : await cached(`job:${await digest(job.jd_text ?? job.url ?? '')}`, JOB_FOR_MS, () =>
              checkJob(job),
            );
      if (sender.tab?.id !== undefined) await showBadge(badgeForMatch(result), sender.tab.id);
      // A new check shows in the popup's grid at once.
      if (result.ok) await markSummaryStale();
      return result;
    }

    case 'preview-job': {
      const key = await digest(request.job.description || request.job.url);
      return cached(`preview:${key}`, JOB_FOR_MS, () => previewJob(request.job));
    }

    case 'record-application': {
      const recorded = await recordApplication(request.job, request.status);
      if (recorded.ok) await markSummaryStale();
      return recorded;
    }

    case 'pending-apply':
      if (request.action === 'set') await pendingApply.setValue(request.value);
      if (request.action === 'clear') await pendingApply.setValue(null);
      return { ok: true, data: await pendingApply.getValue() };

    case 'open-dashboard':
      if (request.path === SETUP_PATH) {
        record('setup_opened', { props: { why: request.from ?? 'popup', tab: 'new' } });
      }
      await browser.tabs.create({ url: await dashboardUrl(request.path) });
      return { ok: true, data: null };

    case 'track-events':
      // Counted for the review ask first: that works with usage sharing off too.
      await updateReview((state) => countEvents(state, request.events, Date.now()));
      // Kept by the background worker and sent in batches (see analytics-queue.ts).
      await enqueue(request.events);
      return { ok: true, data: null };

    case 'summary': {
      const saved = await savedSummary.getValue();
      const due = needsRefresh(saved, request.timezone, Date.now());
      if (!request.refresh || !due) {
        return { ok: true, data: saved && { summary: saved.summary, savedAt: saved.savedAt, due } };
      }
      const fresh = await refreshSummary(request.timezone);
      if (fresh.ok) return { ok: true, data: { summary: fresh.data, savedAt: Date.now(), due: false } };
      // Offline or the server is asleep: the saved numbers are better than none.
      return saved ? { ok: true, data: { summary: saved.summary, savedAt: saved.savedAt, due: true } } : fresh;
    }

    case 'review-ask': {
      if (request.action === 'shown') {
        const state = await updateReview((current) => markAsked(current, Date.now()));
        record('review_asked', { count: applications(state), props: { ask: state.asks } });
      } else if (request.action === 'answer') {
        await updateReview((current) => markAnswered(current, request.answer));
        record('review_answered', { props: { answer: request.answer } });
      }
      const state = await reviewState.getValue();
      // Only the Chrome Web Store link exists so far: Firefox users are not asked.
      const ask = !import.meta.env.FIREFOX && shouldAsk(state, Date.now());
      return { ok: true, data: { ask, applications: applications(state) } };
    }
  }
}

// One fetch at a time: a second popup (or a quick reopen) waits for the same one.
let summaryInFlight: Promise<Result<Summary>> | null = null;

function refreshSummary(timezone: string): Promise<Result<Summary>> {
  summaryInFlight ??= summary(timezone)
    .then(async (result) => {
      if (result.ok) {
        await savedSummary.setValue({ summary: result.data, savedAt: Date.now(), timezone, stale: false });
      }
      return result;
    })
    .finally(() => {
      summaryInFlight = null;
    });
  return summaryInFlight;
}

/** Shown as it is next time, but fetched again: these numbers just changed. */
async function markSummaryStale(): Promise<void> {
  const saved = await savedSummary.getValue();
  if (saved && !saved.stale) await savedSummary.setValue({ ...saved, stale: true });
}

/**
 * The popup's overview: the activity grid and streak, application counts and AI
 * credits, read together. A part that fails is left out rather than failing the
 * whole popup; only when every part fails (offline, signed out) is it an error.
 */
async function summary(timezone: string): Promise<Result<Summary>> {
  const [activity, stats, credits] = await Promise.all([
    api<ActivityYear>(`/activity/me?tz=${encodeURIComponent(timezone)}`, {}, true),
    api<ApplicationStats>('/applications/stats', {}, true),
    api<Credits>('/credits/me', {}, true),
  ]);
  if (!activity.ok && !stats.ok && !credits.ok) return activity;
  return {
    ok: true,
    data: {
      activity: activity.ok ? activity.data : null,
      stats: stats.ok ? stats.data : null,
      credits: credits.ok ? credits.data : null,
    },
  };
}

// Messages arrive together (a page's batch, the popup): changes to the review
// counts are made one after another so none is lost.
let reviewChain: Promise<ReviewState> = Promise.resolve(FRESH);

function updateReview(change: (state: ReviewState) => ReviewState): Promise<ReviewState> {
  reviewChain = reviewChain
    .catch(() => FRESH)
    .then(async () => {
      const before = await reviewState.getValue();
      const after = change(before);
      if (after !== before) await reviewState.setValue(after);
      return after;
    });
  return reviewChain;
}

/** Sets the toolbar badge for one tab, or for every tab without its own when no tab is given. */
async function showBadge(badge: Badge, tabId?: number): Promise<void> {
  // The Firefox build is Manifest V2, where the toolbar button is `browserAction`.
  const button = browser.action ?? browser.browserAction;
  try {
    await button.setBadgeText({ text: badge.text, tabId });
    await button.setBadgeBackgroundColor({ color: badge.color, tabId });
    await button.setTitle({ title: badge.title, tabId });
  } catch {
    // The tab closed meanwhile: there is nothing left to label.
  }
}

type SetupReason = 'install' | 'browser_start' | 'window_opened';

/**
 * A dashboard link. Before the browser is connected it carries this install's id,
 * so the website's setup pages can report how far setting up got.
 */
async function dashboardUrl(path: string): Promise<string> {
  const url = `${DASHBOARD_URL}${path}`;
  if ((await accessKey.getValue()) !== null || (await analyticsOff.getValue())) return url;
  return `${url}${url.includes('?') ? '&' : '?'}install=${await ownInstallId()}`;
}

/** Sends events from before connecting, as this install: no account, no key. */
async function sendAsInstall(events: unknown[]): Promise<'sent' | 'rejected' | 'later'> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/extension/installs/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ install: await installInfo(), events }),
      signal: AbortSignal.timeout(20_000),
    });
    if (response.ok) return 'sent';
    // Invalid, or over the limits: sending the same again cannot help.
    return response.status === 422 || response.status === 429 ? 'rejected' : 'later';
  } catch {
    return 'later';
  }
}

/**
 * The page the browser opens when the extension is removed: it counts the removal
 * for this install and asks why. Without analytics, only the question.
 */
async function setUninstallPage(): Promise<void> {
  const off = await analyticsOff.getValue();
  const version = browser.runtime.getManifest().version;
  const url = off
    ? `${DASHBOARD_URL}/goodbye`
    : `${API_BASE_URL}/api/v1/extension/installs/${await ownInstallId()}/uninstalled?v=${version}`;
  await browser.runtime.setUninstallURL(url).catch(() => undefined);
}

/**
 * Puts the setup in front of the user. A Rolesetu tab that is already open
 * (the browser may have restored one) is brought forward rather than opened
 * twice.
 */
async function showSetup(why: SetupReason): Promise<void> {
  const [open] = await browser.tabs.query({ url: `${DASHBOARD_URL}/*` });
  record('setup_opened', { props: { why, tab: open?.id === undefined ? 'new' : 'existing' } });
  if (open?.id === undefined) {
    await browser.tabs.create({ url: await dashboardUrl(SETUP_PATH) });
    return;
  }
  await browser.tabs.update(open.id, { active: true });
  if (open.windowId !== undefined) await browser.windows.update(open.windowId, { focused: true });
}

// A fresh browser start can report both a start and a first window: one setup is enough.
let showing: Promise<void> | null = null;

/** Shows the setup if this browser is not connected yet. */
function showSetupIfNotConnected(why: SetupReason): void {
  showing ??= accessKey
    .getValue()
    .then((key) => (key === null ? showSetup(why) : undefined))
    .catch((error: unknown) => console.error('Rolesetu: could not open the setup', error))
    .finally(() => {
      showing = null;
    });
}

export default defineBackground(() => {
  // Most people who install never come back to connect, so the setup opens by
  // itself: right after install, and each time the browser is opened until connected.
  browser.runtime.onInstalled.addListener(({ reason, previousVersion }) => {
    if (reason === 'install') {
      record('extension_installed');
      showSetupIfNotConnected('install');
    }
    if (reason === 'update' && previousVersion !== browser.runtime.getManifest().version) {
      record('extension_updated', { props: { from: previousVersion ?? 'unknown' } });
    }
  });
  watchErrors('background', self, (name, payload) => record(name, payload));
  void setUninstallPage();
  analyticsOff.watch(() => void setUninstallPage());
  // The saved popup numbers belong to the account they were fetched for.
  accessKey.watch(() => void savedSummary.removeValue());
  // Sent as the connected user. Before connecting, sent as this install, so the
  // steps of people who never sign in are seen too.
  startAnalytics(async (events) => {
    if ((await accessKey.getValue()) === null) return sendAsInstall(events);
    const install = await ownInstallId();
    const sent = await api<null>('/extension/events', {
      method: 'POST',
      body: JSON.stringify({ events, install }),
    });
    if (sent.ok) return 'sent';
    // Refused as invalid (an event this server does not know yet): sending again cannot help.
    return sent.status === 422 ? 'rejected' : 'later';
  });
  browser.runtime.onStartup.addListener(() => showSetupIfNotConnected('browser_start'));
  // On a Mac, closing every window leaves the browser running, so opening it
  // again is not a start. A first window after none counts as opening it.
  browser.windows.onCreated.addListener((created) => {
    if (created.type !== 'normal') return;
    void browser.windows.getAll({ windowTypes: ['normal'] }).then((all) => {
      if (all.length === 1) showSetupIfNotConnected('window_opened');
    });
  });

  // A "!" on the icon until the browser is connected, so it is clear setup is needed.
  const resting = (key: string | null) => (key === null ? NOT_CONNECTED_BADGE : NO_BADGE);
  void accessKey.getValue().then((key) => showBadge(resting(key)));
  accessKey.watch((key, previous) => {
    void showBadge(resting(key));
    if (key !== null && previous === null) {
      record('extension_connected');
      void flushAnalytics();
    }
    // Another account, or none: nothing kept for the last one may be shown.
    void forget();
  });

  // A tab's score belongs to the page it was given for: reset it when the tab moves on.
  browser.tabs.onUpdated.addListener((tabId, change) => {
    if (change.url === undefined) return;
    void accessKey.getValue().then((key) => showBadge(resting(key), tabId));
  });

  browser.runtime.onMessage.addListener((request: Request, sender, sendResponse) => {
    // Whatever happens in here, the page gets an answer. Without one it would
    // wait forever, or crash trying to read a reply that never came.
    handle(request, sender)
      .catch((error: unknown) => {
        console.error('Rolesetu: request failed', request.type, error);
        return {
          ok: false,
          status: null,
          message: 'Rolesetu ran into a problem. Reload this page and try again.',
        } satisfies Failure;
      })
      .then(sendResponse);
    return true; // the reply is sent asynchronously
  });
});
