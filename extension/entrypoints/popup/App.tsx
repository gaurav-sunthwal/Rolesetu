import { useEffect, useState } from 'react';

import { Mark } from '@/lib/mark';
import { ask } from '@/lib/messages';

export function App() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void ask({ type: 'connection' }).then((result) =>
      setConnected(result.ok ? result.data.connected : false),
    );
  }, []);

  async function checkThisPage() {
    setBusy(true);
    setProblem(null);
    try {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) throw new Error('no tab');
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
          <p>Open Rolesetu, go to Settings, and press “Connect extension”.</p>
          <button
            type="button"
            onClick={() => void ask({ type: 'open-dashboard', path: '/app/settings' })}
          >
            Open Settings
          </button>
        </>
      )}
      {problem ? <p className="error">{problem}</p> : null}
    </>
  );
}
