import { API_BASE_URL, DASHBOARD_URL } from '@/lib/config';
import type {
  AutofillData,
  Failure,
  KeywordCheck,
  Match,
  Request,
  Result,
  Tailored,
  TrackedJob,
} from '@/lib/messages';
import { pendingApply } from '@/lib/session-storage';
import { accessKey } from '@/lib/storage';

const NOT_CONNECTED: Failure = {
  ok: false,
  status: 401,
  message: 'Connect Rolesetu to your account to see your match score.',
};

/** Calls the API as the connected user. Never throws: failures come back as data. */
async function api<T>(path: string, init: RequestInit = {}): Promise<Result<T>> {
  const key = await accessKey.getValue();
  if (!key) return NOT_CONNECTED;

  let response: Response;
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
    return { ok: false, status: null, message: 'Could not reach Rolesetu. Check your connection.' };
  }

  if (response.status === 401) {
    // The key was revoked from the dashboard: forget it, so the UI asks to reconnect.
    await accessKey.setValue(null);
    return NOT_CONNECTED;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === 'string' ? detail : 'Rolesetu could not complete that. Please try again.';
    return { ok: false, status: response.status, message };
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
      url: job.url,
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
      return api<AutofillData>('/extension/autofill');

    case 'keyword-check':
      return api<KeywordCheck>(
        `/tailored-resumes/keywords?match_id=${encodeURIComponent(request.matchId)}`,
      );

    case 'tailor-resume':
      return api<Tailored>('/tailored-resumes', {
        method: 'POST',
        body: JSON.stringify(request.changes),
      });

    case 'keep-resume':
      // The choices are sent, not a file: the server repeats the edit on the saved resume.
      return api('/tailored-resumes/keep', {
        method: 'POST',
        body: JSON.stringify(request.changes),
      });

    case 'connection':
      return { ok: true, data: { connected: (await accessKey.getValue()) !== null } };

    case 'check-job':
      return api<Match>('/matches', {
        method: 'POST',
        body: JSON.stringify({
          jd_text: request.job.description,
          url: request.job.url,
          role: request.job.title,
          company: request.job.company,
        }),
      });

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

export default defineBackground(() => {
  browser.runtime.onMessage.addListener((request: Request, sender, sendResponse) => {
    void handle(request, sender).then(sendResponse);
    return true; // the reply is sent asynchronously
  });
});
