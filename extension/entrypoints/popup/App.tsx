import { useEffect, useState } from 'react';

import { type EventName, newEvent, type TrackPayload } from '@/lib/analytics';
import { SETUP_PATH } from '@/lib/config';
import { Mark } from '@/lib/mark';
import { type ActivityYear, ask, type Credits, type Summary } from '@/lib/messages';
import { analyticsOff } from '@/lib/storage';

import { buildGrid, dayLabel, streakNote } from './grid';

/** Sent at once, not batched: the popup closes itself straight after some of them. */
async function trackNow(name: EventName, payload: TrackPayload = {}, host?: string): Promise<void> {
  await ask({ type: 'track-events', events: [newEvent(name, payload, host)] }).catch(() => undefined);
}

/**
 * Which button in the popup was pressed, so the admin usage page shows what people
 * use and what they ignore. A short fixed name only, never anything about the page.
 */
type Target =
  | 'check_page'
  | 'fill_page'
  | 'dashboard'
  | 'tracker'
  | 'find_jobs'
  | 'resume'
  | 'check_link'
  | 'follow_ups'
  | 'get_pro'
  | 'retry'
  | 'setup'
  | 'settings'
  | 'heatmap';

function clicked(target: Target): Promise<void> {
  return trackNow('popup_clicked', { props: { target } });
}

type Load = { name: 'loading' } | { name: 'ready'; summary: Summary } | { name: 'failed'; message: string };

const QUICK_LINKS = [
  { path: '/app/applications', label: 'Tracker', icon: 'list', target: 'tracker' },
  { path: '/app/jobs', label: 'Find jobs', icon: 'search', target: 'find_jobs' },
  { path: '/app/resume', label: 'Resume', icon: 'file', target: 'resume' },
  { path: '/app/check', label: 'Check a link', icon: 'link', target: 'check_link' },
] as const;

async function openDashboard(path: string, target: Target) {
  await clicked(target);
  await ask({ type: 'open-dashboard', path });
  window.close();
}

export function App() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [load, setLoad] = useState<Load>({ name: 'loading' });
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sharing, setSharing] = useState(true);
  const [settings, setSettings] = useState(false);

  /**
   * The saved numbers first, at once; then a fetch only when they are due (see
   * summary-cache.ts). The fetch updates the view in place without a skeleton.
   */
  function loadSummary() {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const started = Date.now();
    const report = (summary: Summary | null, source: 'saved' | 'fetched' | 'failed') =>
      void trackNow('popup_loaded', {
        count: Date.now() - started,
        props: {
          state: summary?.activity ? 'stats' : 'no_stats',
          source,
          streak: summary?.activity?.streaks.current ?? 0,
          plan: summary?.credits?.plan ?? 'unknown',
          follow_ups: (summary?.stats?.follow_ups_due ?? 0) > 0,
        },
      });

    void ask({ type: 'summary', timezone, refresh: false }).then((saved) => {
      const hit = saved.ok ? saved.data : null;
      if (hit) setLoad({ name: 'ready', summary: hit.summary });
      else setLoad({ name: 'loading' });
      if (hit && !hit.due) return report(hit.summary, 'saved');

      void ask({ type: 'summary', timezone, refresh: true }).then((result) => {
        if (result.ok && result.data) {
          setLoad({ name: 'ready', summary: result.data.summary });
          // Shown from the saved copy first: what was seen first is what counts for speed.
          if (!hit) report(result.data.summary, 'fetched');
          else report(hit.summary, 'saved');
        } else if (!hit) {
          setLoad({ name: 'failed', message: result.ok ? 'Nothing to show yet.' : result.message });
          report(null, 'failed');
        }
      });
    });
  }

  useEffect(() => {
    void ask({ type: 'connection' }).then((result) => {
      const yes = result.ok ? result.data.connected : false;
      setConnected(yes);
      if (yes) loadSummary();
      else void trackNow('popup_loaded', { props: { state: 'signed_out' } });
    });
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
      await clicked('check_page');
      await trackNow('page_checked', {}, tab.url ? new URL(tab.url).hostname.replace(/^www\./, '') : undefined);
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
      setProblem('This page can’t be checked. Browser pages and the web store are off limits.');
      setBusy(false);
    }
  }

  /** Fills the form on this tab even when Rolesetu did not take the page for one. */
  async function fillThisPage() {
    setBusy(true);
    setProblem(null);
    try {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) throw new Error('no tab');
      await clicked('fill_page');
      // The form may sit in a frame: count each frame's fields and use the frame with the most.
      const counts = await browser.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        func: () => document.querySelectorAll('input:not([type="hidden"]), textarea, select, [contenteditable="true"]').length,
      });
      const best = counts
        .filter((frame) => (frame.result ?? 0) > 0)
        .sort((a, b) => (b.result ?? 0) - (a.result ?? 0))[0];
      if (!best) {
        setProblem('There is no form on this page to fill.');
        setBusy(false);
        return;
      }
      const target = { tabId: tab.id, frameIds: [best.frameId] };
      await browser.scripting.executeScript({
        target,
        func: () => {
          window.__rolesetuFill = true;
        },
      });
      await browser.scripting.executeScript({ target, files: ['/content-scripts/job.js'] });
      window.close();
    } catch {
      setProblem('This page can’t be filled. Browser pages and the web store are off limits.');
      setBusy(false);
    }
  }

  const credits = load.name === 'ready' ? load.summary.credits : null;

  return (
    <>
      <header>
        <Mark />
        <strong>Rolesetu</strong>
        {credits ? <span className={`plan ${credits.plan}`}>{credits.plan === 'pro' ? 'Pro' : 'Free'}</span> : null}
        <span className="header-actions">
          {connected ? (
            <button
              type="button"
              className="icon-btn"
              title="Open dashboard"
              aria-label="Open dashboard"
              onClick={() => void openDashboard('/app', 'dashboard')}
            >
              <Icon name="external" />
            </button>
          ) : null}
          <button
            type="button"
            className={settings ? 'icon-btn on' : 'icon-btn'}
            title="Settings"
            aria-label="Settings"
            aria-expanded={settings}
            onClick={() => {
              if (!settings) void clicked('settings');
              setSettings(!settings);
            }}
          >
            <Icon name="gear" />
          </button>
        </span>
      </header>

      {settings ? (
        <section className="settings" aria-label="Settings">
          <label className="setting">
            <input
              type="checkbox"
              checked={sharing}
              onChange={(event) => void setSharingUsage(event.target.checked)}
            />
            <span>
              <b>Share usage to improve Rolesetu</b>
              Which features are used, never what you type or the pages you visit.
            </span>
          </label>
        </section>
      ) : null}

      {connected === null ? (
        <Skeleton />
      ) : connected ? (
        <>
          {load.name === 'loading' ? (
            <Skeleton />
          ) : load.name === 'failed' ? (
            <p className="note">
              Your stats didn’t load. {load.message}{' '}
              <button
                type="button"
                className="link"
                onClick={() => {
                  void clicked('retry');
                  loadSummary();
                }}
              >
                Try again
              </button>
            </p>
          ) : (
            <Overview summary={load.summary} />
          )}

          <button type="button" className="primary" onClick={() => void checkThisPage()} disabled={busy}>
            {busy ? 'Reading the page…' : 'Check this page'}
          </button>
          <button type="button" className="secondary" onClick={() => void fillThisPage()} disabled={busy}>
            Fill a form on this page
          </button>
          {problem ? <p className="error">{problem}</p> : null}

          <nav className="quick" aria-label="Open in the dashboard">
            {QUICK_LINKS.map((link) => (
              <button key={link.path} type="button" onClick={() => void openDashboard(link.path, link.target)}>
                <Icon name={link.icon} />
                {link.label}
              </button>
            ))}
          </nav>

          {credits ? <CreditsBar credits={credits} /> : null}
        </>
      ) : (
        <SignedOut />
      )}
    </>
  );
}

function Overview({ summary }: { summary: Summary }) {
  const { activity, stats } = summary;
  const streak = activity?.streaks.current ?? 0;
  return (
    <>
      <section className="tiles" aria-label="Your job hunt">
        {/* The grid's own count, so the tile and the squares agree. */}
        <Tile value={activity?.totals.applications ?? stats?.total} label="Applied" />
        <Tile value={stats?.interviews} label="Interviews" />
        <Tile value={streak} label="Day streak" accent={streak > 0} />
      </section>
      {stats && stats.follow_ups_due > 0 ? (
        <button type="button" className="due" onClick={() => void openDashboard('/app/applications', 'follow_ups')}>
          <Icon name="bell" />
          {stats.follow_ups_due} follow-up{stats.follow_ups_due === 1 ? '' : 's'} due
          <span aria-hidden>→</span>
        </button>
      ) : null}
      {activity ? <Heatmap activity={activity} /> : null}
    </>
  );
}

function Tile({ value, label, accent = false }: { value: number | undefined; label: string; accent?: boolean }) {
  return (
    <div className={accent ? 'tile accent' : 'tile'}>
      <span className="value">
        {accent ? <Icon name="flame" /> : null}
        {value ?? '–'}
      </span>
      <span className="label">{label}</span>
    </div>
  );
}

function Heatmap({ activity }: { activity: ActivityYear }) {
  const grid = buildGrid(activity.days);
  const [looked, setLooked] = useState(false);
  return (
    <section
      className="heat"
      aria-labelledby="heat-title"
      onMouseEnter={() => {
        // Counted once per opening: do people look at the grid at all?
        if (looked) return;
        setLooked(true);
        void clicked('heatmap');
      }}
    >
      <div className="heat-head">
        <h2 id="heat-title">Last {grid.weeks} weeks</h2>
        <span>
          {grid.applied} applied · {grid.checked} checked
        </span>
      </div>
      <div className="cells" style={{ gridTemplateColumns: `repeat(${grid.weeks}, 1fr)` }} role="img"
        aria-label={`${grid.applied} jobs applied and ${grid.checked} checked in the last ${grid.weeks} weeks`}>
        {grid.cells.map((cell) => (
          <i
            key={cell.date}
            className={`l${cell.level}${cell.today ? ' today' : ''}`}
            style={{ gridColumn: cell.column + 1, gridRow: cell.row + 1 }}
            title={`${dayLabel(cell.date)}: ${cell.applied} applied, ${cell.checked} checked`}
          />
        ))}
      </div>
      <div className="heat-foot">
        <span>{streakNote(activity)}</span>
        <span className="legend" aria-hidden>
          Less <i className="l0" /><i className="l1" /><i className="l2" /><i className="l3" /><i className="l4" /> More
        </span>
      </div>
    </section>
  );
}

function CreditsBar({ credits }: { credits: Credits }) {
  const share = credits.limit > 0 ? Math.min(1, credits.left / credits.limit) : 0;
  const resets = new Date(credits.resets_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  return (
    <section className="credits" aria-label="AI credits">
      <div className="credits-head">
        <span>
          AI credits <b>{credits.left}</b> of {credits.limit} left
        </span>
        {credits.plan === 'free' ? (
          <button type="button" className="link" onClick={() => void openDashboard('/app/plan', 'get_pro')}>
            Get Pro
          </button>
        ) : (
          <span className="muted">Resets {resets}</span>
        )}
      </div>
      <div className={share < 0.2 ? 'bar low' : 'bar'} role="progressbar" aria-valuemin={0}
        aria-valuemax={credits.limit} aria-valuenow={credits.left}>
        <span style={{ width: `${share * 100}%` }} />
      </div>
      {credits.plan === 'free' ? (
        <p className="muted small">Resets {resets}. Pro gives {credits.pro_limit} a month.</p>
      ) : null}
    </section>
  );
}

function SignedOut() {
  return (
    <>
      <div className="status off">
        <i />
        Not connected
      </div>
      <ul className="perks">
        <li>See your match score on every job page</li>
        <li>Autofill applications in one click</li>
        <li>Track every job and keep your streak</li>
      </ul>
      <button type="button" className="primary" onClick={() => void openDashboard(SETUP_PATH, 'setup')}>
        Set up Rolesetu, it’s free
      </button>
    </>
  );
}

function Skeleton() {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      <div className="sk tiles-sk" />
      <div className="sk heat-sk" />
    </div>
  );
}

const PATHS: Record<string, string> = {
  external: 'M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
  file: 'M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7zM14 3v4h4M9 13h6M9 17h6',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 21h4',
  gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  flame: 'M12 21c-3.9 0-7-2.7-7-6.5 0-3.3 2.4-5.5 4-7.5.4 2 1.6 3 2.5 3.5C11.5 7 13 4.5 14.5 3c.5 3 4.5 5.5 4.5 11.5 0 3.8-3.1 6.5-7 6.5z',
};

function Icon({ name }: { name: string }) {
  return (
    <svg className="ico" viewBox="0 0 24 24" aria-hidden>
      <path d={PATHS[name]} />
    </svg>
  );
}
