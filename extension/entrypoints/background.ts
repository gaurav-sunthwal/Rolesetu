import { fitJob, fitUrl, type JobRequest, messageFor, UNREACHABLE } from '@/lib/api-errors';
import { type Badge, badgeForMatch, NO_BADGE, NOT_CONNECTED_BADGE } from '@/lib/badge';
import { API_BASE_URL, DASHBOARD_URL, SETUP_PATH } from '@/lib/config';
import type {
  AutofillData,
  Failure,
  KeywordCheck,
  LearnedAnswerRead,
  Match,
  Request,
  Result,
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
import { pendingApply } from '@/lib/session-storage';
import { accessKey } from '@/lib/storage';

const NOT_CONNECTED: Failure = {
  ok: false,
  status: 401,
  message: 'Connect Rolesetu to your account to see your match score.',
};

// First try at once, then again after a short and a longer pause.
const RETRY_AFTER_MS = [0, 1500, 4000];
// What a host answers while the server behind it is still coming up.
const STARTING_UP = new Set([502, 503, 504]);

/** Calls the API as the connected user. Never throws: failures come back as data. */
async function api<T>(path: string, init: RequestInit = {}): Promise<Result<T>> {
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
        signal: AbortSignal.timeout(25_000),
      });
    } catch {
      response = null;
      continue;
    }
    if (!STARTING_UP.has(response.status)) break;
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

/** Loads the score and autofill UI into the frame whose detector found something. */
async function activate(sender: Browser.runtime.MessageSender): Promise<Result<null>> {
  const tabId = sender.tab?.id;
  if (tabId === undefined) return { ok: false, status: null, message: 'No page to show this on.' };
  try {
    await browser.scripting.executeScript({
      target: { tabId, frameIds: [sender.frameId ?? 0] },
      files: ['/content-scripts/job.js'],
    });
    return { ok: true, data: null };
  } catch {
    return { ok: false, status: null, message: 'Rolesetu cannot run on this page.' };
  }
}

async function handle(request: Request, sender: Browser.runtime.MessageSender): Promise<unknown> {
  switch (request.type) {
    case 'activate':
      return activate(sender);

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
      return result;
    }

    case 'record-application':
      return recordApplication(request.job, request.status);

    case 'pending-apply':
      if (request.action === 'set') await pendingApply.setValue(request.value);
      if (request.action === 'clear') await pendingApply.setValue(null);
      return { ok: true, data: await pendingApply.getValue() };

    case 'open-dashboard':
      await browser.tabs.create({ url: `${DASHBOARD_URL}${request.path}` });
      return { ok: true, data: null };
  }
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

/**
 * Puts the setup in front of the user. A Rolesetu tab that is already open
 * (the browser may have restored one) is brought forward rather than opened
 * twice.
 */
async function showSetup(): Promise<void> {
  const [open] = await browser.tabs.query({ url: `${DASHBOARD_URL}/*` });
  if (open?.id === undefined) {
    await browser.tabs.create({ url: `${DASHBOARD_URL}${SETUP_PATH}` });
    return;
  }
  await browser.tabs.update(open.id, { active: true });
  if (open.windowId !== undefined) await browser.windows.update(open.windowId, { focused: true });
}

// A fresh browser start can report both a start and a first window: one setup is enough.
let showing: Promise<void> | null = null;

/** Shows the setup if this browser is not connected yet. */
function showSetupIfNotConnected(): void {
  showing ??= accessKey
    .getValue()
    .then((key) => (key === null ? showSetup() : undefined))
    .catch((error: unknown) => console.error('Rolesetu: could not open the setup', error))
    .finally(() => {
      showing = null;
    });
}

export default defineBackground(() => {
  // Most people who install never come back to connect, so the setup opens by
  // itself: right after install, and each time the browser is opened until connected.
  browser.runtime.onInstalled.addListener(({ reason }) => {
    if (reason === 'install') showSetupIfNotConnected();
  });
  browser.runtime.onStartup.addListener(showSetupIfNotConnected);
  // On a Mac, closing every window leaves the browser running, so opening it
  // again is not a start. A first window after none counts as opening it.
  browser.windows.onCreated.addListener((created) => {
    if (created.type !== 'normal') return;
    void browser.windows.getAll({ windowTypes: ['normal'] }).then((all) => {
      if (all.length === 1) showSetupIfNotConnected();
    });
  });

  // A "!" on the icon until the browser is connected, so it is clear setup is needed.
  const resting = (key: string | null) => (key === null ? NOT_CONNECTED_BADGE : NO_BADGE);
  void accessKey.getValue().then((key) => showBadge(resting(key)));
  accessKey.watch((key) => {
    void showBadge(resting(key));
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
