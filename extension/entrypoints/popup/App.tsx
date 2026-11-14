import { useEffect, useState } from 'react';

import { type EventName, newEvent } from '@/lib/analytics';
import { SETUP_PATH } from '@/lib/config';
import { Mark } from '@/lib/mark';
import { ask } from '@/lib/messages';
import { analyticsOff } from '@/lib/storage';

/** Sent at once, not batched: the popup closes itself straight after some of them. */
async function trackNow(name: EventName, host?: string): Promise<void> {
  await ask({ type: 'track-events', events: [newEvent(name, {}, host)] }).catch(() => undefined);
}

export function App() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sharing, setSharing] = useState(true);

  useEffect(() => {
    void ask({ type: 'connection' }).then((result) =>
      setConnected(result.ok ? result.data.connected : false),
    );
    void analyticsOff.getValue().then((off) => setSharing(!off));
    void trackNow('popup_opened');
  }, []);

  async function setSharingUsage(on: boolean) {
    setSharing(on);
    await analyticsOff.setValue(!on);
  }

  async function checkThisPage() {
    setBusy(true);
    setProblem(null);
    try {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) throw new Error('no tab');
      await trackNow('page_checked', tab.url ? new URL(tab.url).hostname.replace(/^www\./, '') : undefined);
      // Tell the page script the user asked for it, then run it on this tab.
      await browser.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          window.__rolesetuManual = true;
        },
      });
      await browser.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['/content-scripts/job.js'],
      });
      window.close();
    } catch {
      setProblem('This page cannot be checked. Browser pages and the web store are off limits.');
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <Mark />
        Rolesetu
      </header>

      {connected === null ? (
        <p>Checking…</p>
      ) : connected ? (
        <>
          <div className="status">
            <i />
            Connected to your account
          </div>
          <p>
            Your match score appears by itself on any job page. If a page was missed, check it here.
          </p>
          <button type="button" onClick={() => void checkThisPage()} disabled={busy}>
            {busy ? 'Reading the page…' : 'Check this page'}
          </button>
        </>
      ) : (
        <>
          <div className="status off">
            <i />
            Not connected
          </div>
          <p>
            Sign in, add your resume, and connect this browser. Then your match score shows on every
            job page.
          </p>
          <button
            type="button"
            onClick={() => void ask({ type: 'open-dashboard', path: SETUP_PATH })}
          >
            Set up Rolesetu
          </button>
        </>
      )}
      {problem ? <p className="error">{problem}</p> : null}
      <label className="setting">
        <input type="checkbox" checked={sharing} onChange={(event) => void setSharingUsage(event.target.checked)} />
        Share how I use Rolesetu (which features, never what I type or the pages I visit)
      </label>
    </>
  );
}
