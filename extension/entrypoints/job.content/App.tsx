import { useCallback, useEffect, useRef, useState } from 'react';
import type { ContentScriptContext } from '#imports';

import { hasApplicationForm } from '@/lib/autofill/fields';
import { fill, planAutofill } from '@/lib/autofill/fill';
import { detectJob } from '@/lib/job-detect';
import { projectedScore } from '@/lib/projected-score';
import {
  ask,
  type AutofillData,
  type DetectedJob,
  type KeywordCheck,
  type Match,
  type PendingApply,
  type SkillResult,
  type Tailored,
  type TailorRequest,
  type TrackedJob,
} from '@/lib/messages';

import { type PillState, removeApplyPills, showApplyPills } from './apply-pill';
import { applyActionOf, PENDING_FOR_MS, watchForConfirmation } from './apply-tracking';

type Phase =
  | { name: 'looking' }
  | { name: 'no-job' }
  | { name: 'disconnected' }
  | { name: 'scoring'; job: DetectedJob }
  | { name: 'ready'; job: DetectedJob; match: Match }
  | { name: 'error'; message: string };

const DETECT_ATTEMPTS = 6;
const DETECT_EVERY_MS = 700;
const VERDICT = {
  strong: { label: 'Strong', color: 'var(--good)' },
  partial: { label: 'Partial', color: 'var(--warn)' },
  missing: { label: 'Missing', color: 'var(--bad)' },
} as const;

function bandOf(score: number) {
  if (score >= 75) return { label: 'Strong fit', color: 'var(--good)' };
  if (score >= 50) return { label: 'Worth a shot', color: 'var(--brand)' };
  return { label: 'A stretch', color: 'var(--warn)' };
}

function bandColor(score: number): string {
  // The pill sits in the host page, outside our styles, so it needs real colours.
  if (score >= 75) return '#1f9d55';
  if (score >= 50) return '#2f5fe0';
  return '#d98a00';
}

function pillFor(phase: Phase): PillState {
  if (phase.name === 'scoring') return { text: 'Checking your fit…', color: '#9aa0ac' };
  if (phase.name !== 'ready') return null;
  const score = phase.match.score ?? 0;
  // Falling short on experience is said on the button itself: it matters more
  // than the band, and it is the thing most easily overlooked.
  const short = experienceGap(phase.match);
  return {
    text: short ? `${score}% match · ${short}` : `${score}% match · ${bandOf(score).label}`,
    color: short ? '#d98a00' : bandColor(score),
  };
}

function yearsLabel(value: number, orMore = false): string {
  const plus = orMore ? '+' : '';
  if (value > 0 && value < 1) return `${Math.round(value * 12)}${plus} mo`;
  return `${value}${plus} yr${value === 1 ? '' : 's'}`;
}

/** "Needs 5+ yrs" when the job asks for more experience than the profile shows. */
function experienceGap(match: Match): string | null {
  const experience = match.experience;
  if (!experience || experience.required_min === null) return null;
  if (experience.status !== 'short' && experience.status !== 'well_short') return null;
  return `Needs ${yearsLabel(experience.required_min, true)}`;
}

const EXPERIENCE_TITLE = {
  meets: 'Experience: you meet it',
  open_to_freshers: 'Experience: open to freshers',
  short: 'Experience: slightly short',
  well_short: 'Experience: well short',
  not_stated: 'Experience: not stated',
} as const;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Pages often fill in after load, so look a few times before giving up. */
async function findJob(strict: boolean): Promise<DetectedJob | null> {
  for (let attempt = 0; attempt < DETECT_ATTEMPTS; attempt += 1) {
    const job = detectJob(document, window.location.href, strict);
    if (job) return job;
    await wait(DETECT_EVERY_MS);
  }
  return null;
}

function trackedJobOf(job: DetectedJob, match: Match): TrackedJob {
  return {
    matchId: match.id,
    // What the page itself calls the job wins over a title the server worked out.
    role: job.title ?? match.role ?? 'Untitled role',
    company: job.company ?? match.company ?? 'Company not stated',
    url: job.url,
  };
}

type Notice =
  | { kind: 'applied'; job: TrackedJob }
  | { kind: 'ask'; job: TrackedJob }
  | { kind: 'failed'; job: TrackedJob; message: string };

/**
 * Keeps the application tracker in step with what the user does on the page:
 * saved on the Apply click, applied once the site confirms it, and a question
 * when they went elsewhere to apply and came back.
 */
function useApplyTracking(current: TrackedJob | null) {
  const [notice, setNotice] = useState<Notice | null>(null);
  // True while the tracker is being updated, so the button that was pressed can say so.
  const [saving, setSaving] = useState(false);
  const pending = useRef<PendingApply | null>(null);
  const stopWatching = useRef<() => void>(() => {});
  const leftAt = useRef<number | null>(null);
  const job = useRef(current);
  job.current = current;

  const markApplied = useCallback(async (applied: TrackedJob) => {
    stopWatching.current();
    pending.current = null;
    void ask({ type: 'pending-apply', action: 'clear' });
    setSaving(true);
    const result = await ask({ type: 'record-application', job: applied, status: 'applied' });
    setSaving(false);
    setNotice(
      result.ok
        ? { kind: 'applied', job: applied }
        : { kind: 'failed', job: applied, message: result.message },
    );
  }, []);

  const dismiss = useCallback(() => {
    pending.current = null;
    stopWatching.current();
    void ask({ type: 'pending-apply', action: 'clear' });
    setNotice(null);
  }, []);

  useEffect(() => {
    // An application started on an earlier page of this site may finish here.
    void ask({ type: 'pending-apply', action: 'get' }).then((result) => {
      const stored = result.ok ? result.data : null;
      if (!stored || Date.now() - stored.startedAt > PENDING_FOR_MS) return;
      pending.current = stored;
      stopWatching.current = watchForConfirmation(() => void markApplied(stored), false);
    });

    const onClick = (event: MouseEvent) => {
      const action = applyActionOf(event.target);
      if (action === null) return;
      const started = job.current ? { ...job.current, startedAt: Date.now() } : pending.current;
      if (!started) return; // a button on a page where no job was scored
      if (action === 'apply' && job.current) {
        pending.current = started;
        void ask({ type: 'pending-apply', action: 'set', value: started });
        // In the tracker straight away, so it is not lost if they never finish.
        void ask({ type: 'record-application', job: started, status: 'saved' });
      }
      stopWatching.current();
      stopWatching.current = watchForConfirmation(() => void markApplied(started), true);
    };

    const onVisibility = () => {
      if (document.hidden) {
        leftAt.current = Date.now();
        return;
      }
      // Back after a while with an application still open: they probably
      // applied on another site, which cannot be seen from here. Ask.
      const away = leftAt.current ? Date.now() - leftAt.current : 0;
      leftAt.current = null;
      if (pending.current && away > 8000) setNotice({ kind: 'ask', job: pending.current });
    };

    document.addEventListener('click', onClick, true);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('visibilitychange', onVisibility);
      stopWatching.current();
    };
  }, [markApplied]);

  // Stable, so the notice's auto-dismiss timer is not restarted on every render.
  const clearNotice = useCallback(() => setNotice(null), []);
  return { notice, saving, markApplied, dismiss, clearNotice };
}

type Autofill =
  | { name: 'none' }
  | { name: 'offer'; count: number }
  | { name: 'connect' }
  | { name: 'filled'; count: number }
  | { name: 'failed'; message: string };

const RESCAN_AFTER_MS = 800;

/**
 * Offers to fill an application form from the user's profile. The form is
 * looked for again whenever the page changes, because the next step of an
 * application usually appears without a reload.
 */
function useAutofill(ctx: ContentScriptContext) {
  const [state, setState] = useState<Autofill>({ name: 'none' });
  const data = useRef<AutofillData | null>(null);
  const dismissed = useRef(false);
  // A "filled" or "failed" message stays until it is closed or times out.
  const holding = useRef(false);

  const scan = useCallback(async () => {
    if (ctx.isInvalid || dismissed.current || holding.current) return;
    if (!hasApplicationForm(document)) return setState({ name: 'none' });

    if (data.current === null) {
      const result = await ask({ type: 'autofill-data' });
      if (!result.ok) {
        // Only "not connected" is worth interrupting for; anything else stays quiet.
        return setState(result.status === 401 ? { name: 'connect' } : { name: 'none' });
      }
      data.current = result.data;
    }
    const count = planAutofill(document, data.current).length;
    setState(count > 0 ? { name: 'offer', count } : { name: 'none' });
  }, [ctx]);

  useEffect(() => {
    void scan();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => void scan(), RESCAN_AFTER_MS);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [scan]);

  const run = useCallback(() => {
    if (data.current === null) return;
    const count = fill(planAutofill(document, data.current));
    holding.current = true;
    setState(
      count > 0
        ? { name: 'filled', count }
        : { name: 'failed', message: 'This form did not accept the values. Please fill it by hand.' },
    );
  }, []);

  const close = useCallback(() => {
    // Closing the offer means "not on this page"; closing a result just clears it.
    if (!holding.current) dismissed.current = true;
    holding.current = false;
    setState({ name: 'none' });
    void scan();
  }, [scan]);

  return { state, run, close };
}

export function App({ ctx, manual }: { ctx: ContentScriptContext; manual: boolean }) {
  const [phase, setPhase] = useState<Phase>({ name: 'looking' });
  const [open, setOpen] = useState(manual);
  // How many of the page's Apply buttons carry the score. When none do, the
  // floating badge is shown instead.
  const [pills, setPills] = useState(0);
  const run = useRef(0);
  // The address the panel's contents belong to.
  const shownFor = useRef(window.location.href);
  // Kept here, above the panel, so closing and reopening the panel does not lose
  // an updated resume the user has not downloaded or saved yet.
  const [tailoring, setTailoring] = useState<Tailoring>({ name: 'idle' });

  const check = useCallback(async () => {
    const id = (run.current += 1);
    const stale = () => id !== run.current || ctx.isInvalid;
    setPhase({ name: 'looking' });

    // Asked for by the user: take the page's word. Found by ourselves: be sure.
    const job = await findJob(!manual);
    if (stale()) return;
    if (!job) return setPhase({ name: 'no-job' });

    const connection = await ask({ type: 'connection' });
    if (stale()) return;
    if (!connection.ok || !connection.data.connected) return setPhase({ name: 'disconnected' });

    setPhase({ name: 'scoring', job });
    const result = await ask({ type: 'check-job', job });
    if (stale()) return;
    if (result.ok) setPhase({ name: 'ready', job, match: result.data });
    else if (result.status === 401) setPhase({ name: 'disconnected' });
    else setPhase({ name: 'error', message: result.message });
  }, [ctx, manual]);

  // The profile changed (skills were added), so the same job is scored again
  // in the background. The panel stays as it is until the new score arrives.
  const rescore = useCallback(async (job: DetectedJob) => {
    const id = run.current;
    const result = await ask({ type: 'check-job', job });
    if (result.ok && id === run.current) setPhase({ name: 'ready', job, match: result.data });
  }, []);

  useEffect(() => {
    void check();
    // Job sites swap listings without reloading the page; score the new one.
    ctx.addEventListener(window, 'wxt:locationchange', () => {
      // The browser also reports a file download as a navigation. The page
      // has not changed then, and closing the panel would throw away the
      // resume the user just asked to download.
      if (window.location.href === shownFor.current) return;
      shownFor.current = window.location.href;
      setOpen(false);
      setTailoring({ name: 'idle' });
      void check();
    });
    const reopen = () => setOpen(true);
    window.addEventListener('rolesetu:open', reopen);
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('rolesetu:open', reopen);
      window.removeEventListener('keydown', onKey);
    };
  }, [check, ctx]);

  const tracking = useApplyTracking(
    phase.name === 'ready' ? trackedJobOf(phase.job, phase.match) : null,
  );

  // Show the score beside the page's own Apply button, and keep it there while
  // the page re-renders (job sites redraw these buttons often).
  useEffect(() => {
    const state = pillFor(phase);
    if (state === null) {
      removeApplyPills();
      setPills(0);
      return;
    }
    const place = () => setPills(showApplyPills(state, () => setOpen(true)));
    place();

    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new MutationObserver((changes) => {
      // Our own pills being added or removed must not trigger another pass.
      const external = changes.some((change) =>
        [...change.addedNodes, ...change.removedNodes].some(
          (node) => !(node instanceof Element && node.hasAttribute('data-rolesetu-pill')),
        ),
      );
      if (!external) return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (document.querySelector('[data-rolesetu-pill]') === null) place();
      }, 400);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      clearTimeout(timer);
      removeApplyPills();
    };
  }, [phase]);

  const autofill = useAutofill(ctx);
  const autofillCard =
    autofill.state.name === 'none' ? null : (
      <AutofillCard state={autofill.state} onFill={autofill.run} onClose={autofill.close} />
    );

  const notice = tracking.notice ? (
    <NoticeCard
      notice={tracking.notice}
      saving={tracking.saving}
      onYes={(job) => void tracking.markApplied(job)}
      onNo={tracking.dismiss}
      onClose={tracking.clearNotice}
    />
  ) : null;

  // On a page that is not a job, stay out of the way unless the user asked.
  if ((phase.name === 'no-job' || phase.name === 'looking') && !open) {
    return notice || autofillCard ? (
      <div className="aa">
        {notice}
        {autofillCard}
      </div>
    ) : null;
  }

  return (
    <div className="aa">
      {notice}
      {autofillCard}
      {open ? (
        <Panel
          phase={phase}
          tailoring={tailoring}
          setTailoring={setTailoring}
          onClose={() => setOpen(false)}
          onRetry={check}
          onRescore={rescore}
        />
      ) : pills > 0 ? null : (
        // No Apply button to attach to (or nothing to show there): float instead.
        <Badge phase={phase} onOpen={() => setOpen(true)} />
      )}
    </div>
  );
}

function Ring({ score, big }: { score: number; big?: boolean }) {
  const radius = 15;
  const length = 2 * Math.PI * radius;
  return (
    <div className={big ? 'ring big' : 'ring'} role="img" aria-label={`Match score ${score} out of 100`}>
      <svg viewBox="0 0 36 36">
        <circle cx="18" cy="18" r={radius} fill="none" stroke="var(--line)" strokeWidth="3.5" />
        <circle
          cx="18"
          cy="18"
          r={radius}
          fill="none"
          stroke={bandOf(score).color}
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeDasharray={length}
          strokeDashoffset={length * (1 - score / 100)}
        />
      </svg>
      <span>{score}</span>
    </div>
  );
}

function Badge({ phase, onOpen }: { phase: Phase; onOpen: () => void }) {
  if (phase.name === 'ready') {
    const score = phase.match.score ?? 0;
    return (
      <button type="button" className="badge" onClick={onOpen}>
        <Ring score={score} />
        <span>
          <span className="label">{experienceGap(phase.match) ?? bandOf(score).label}</span>
          <br />
          <span className="sub">See why</span>
        </span>
      </button>
    );
  }
  const label =
    phase.name === 'scoring'
      ? 'Checking your fit…'
      : phase.name === 'disconnected'
        ? 'Connect Rolesetu'
        : 'Could not score this job';
  return (
    <button type="button" className="badge" onClick={onOpen}>
      {phase.name === 'scoring' ? <span className="spin" /> : <span className="dot">R</span>}
      <span className="label">{label}</span>
    </button>
  );
}

function Panel({
  phase,
  tailoring,
  setTailoring,
  onClose,
  onRetry,
  onRescore,
}: {
  phase: Phase;
  tailoring: Tailoring;
  setTailoring: (next: Tailoring) => void;
  onClose: () => void;
  onRetry: () => void;
  onRescore: (job: DetectedJob) => void;
}) {
  return (
    <section className="panel" role="dialog" aria-label="Rolesetu match score">
      <header className="head">
        <span className="dot" style={{ marginLeft: 0 }}>
          R
        </span>
        <strong>Rolesetu</strong>
        <button type="button" className="icon" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </header>

      {phase.name === 'ready' ? (
        <Result
          job={phase.job}
          match={phase.match}
          tailoring={tailoring}
          setTailoring={setTailoring}
          onRescore={() => onRescore(phase.job)}
        />
      ) : (
        <div className="body">
          <div className="center">
            {phase.name === 'looking' || phase.name === 'scoring' ? (
              <>
                <span className="spin" />
                <strong>
                  {phase.name === 'looking' ? 'Reading this page…' : 'Checking your fit…'}
                </strong>
              </>
            ) : phase.name === 'disconnected' ? (
              <>
                <strong>Connect to your account</strong>
                <span className="muted">
                  Open Rolesetu, go to Settings and press “Connect extension”. Then come back to
                  this page.
                </span>
                <button
                  type="button"
                  className="btn primary"
                  style={{ flex: 'none', padding: '0 20px' }}
                  onClick={() => void ask({ type: 'open-dashboard', path: '/app/settings' })}
                >
                  Open Settings
                </button>
              </>
            ) : phase.name === 'no-job' ? (
              <>
                <strong>No job found on this page</strong>
                <span className="muted">
                  Open a single job listing (not a list of results) and try again.
                </span>
              </>
            ) : (
              <>
                <strong>This job could not be scored</strong>
                <span className="muted">{phase.message}</span>
                <button
                  type="button"
                  className="btn"
                  style={{ flex: 'none', padding: '0 20px' }}
                  onClick={onRetry}
                >
                  Try again
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

const MAX_SKILLS = 12;

type Tailoring =
  | { name: 'idle' }
  | { name: 'working' }
  | { name: 'done'; result: Tailored; changes: TailorRequest }
  | { name: 'failed'; message: string };

type Keywords =
  | { name: 'loading' }
  | { name: 'ready'; check: KeywordCheck }
  | { name: 'failed'; message: string; noResume: boolean };

function downloadPdf(tailored: Tailored) {
  const bytes = Uint8Array.from(atob(tailored.pdf), (char) => char.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = tailored.filename;
  link.click();
  URL.revokeObjectURL(url);
}

function toggled(list: string[], name: string): string[] {
  if (list.includes(name)) return list.filter((item) => item !== name);
  return list.length < MAX_SKILLS ? [...list, name] : list;
}

function Result({
  job,
  match,
  tailoring,
  setTailoring,
  onRescore,
}: {
  job: DetectedJob;
  match: Match;
  tailoring: Tailoring;
  setTailoring: (next: Tailoring) => void;
  onRescore: () => void;
}) {
  const [tracking, setTracking] = useState<'idle' | 'saving' | 'done' | 'failed'>('idle');
  // Skills ticked below. The ring shows where the score would land with them.
  const [ticked, setTicked] = useState<string[]>([]);
  const current = match.score ?? 0;
  const { score, heldBack } = projectedScore(match, ticked);
  const band = bandOf(score);
  // What the page itself calls the job always wins; a title worked out by the
  // server is only a stand-in for when the page gave none.
  const role = job.title ?? match.role ?? 'Untitled role';
  const company = job.company ?? match.company ?? 'Company not stated';
  const required = match.skill_results.filter((skill) => skill.required);
  const niceToHave = match.skill_results.filter((skill) => !skill.required);

  async function track() {
    setTracking('saving');
    const result = await ask({
      type: 'record-application',
      job: trackedJobOf(job, match),
      status: 'saved',
    });
    setTracking(result.ok ? 'done' : 'failed');
  }

  return (
    <>
      <div className="body">
        <div className="summary">
          <Ring score={score} big />
          <div>
            <span className="band" style={{ color: band.color }}>
              {band.label}
            </span>
            <h2>{role}</h2>
            <span className="muted small">{company}</span>
          </div>
        </div>
        {score > current ? (
          <p className="gain" role="status">
            <b>
              {current} → {score}
            </b>
            <span className="up">+{score - current}</span>
            <span className="muted">with the skills you ticked, once saved</span>
          </p>
        ) : heldBack ? (
          <p className="muted small">
            The skills you ticked will not raise this score: it is held at {match.score_cap} by the
            experience this job asks for.
          </p>
        ) : null}
        {match.experience ? (
          <section className={`note ${match.experience.status}`} aria-label="Experience">
            <strong>{EXPERIENCE_TITLE[match.experience.status]}</strong>
            <div className="facts">
              <span>
                Job asks{' '}
                <b>
                  {match.experience.required_min === null
                    ? 'not stated'
                    : match.experience.required_min === 0
                      ? 'none'
                      : yearsLabel(match.experience.required_min, true)}
                </b>
              </span>
              <span>
                You have <b>{yearsLabel(match.experience.candidate_years)}</b>
              </span>
            </div>
            <p>{match.experience.summary}</p>
          </section>
        ) : match.seniority_note ? (
          <p className="note">{match.seniority_note}</p>
        ) : null}

        <ResumeMatcher
          matchId={match.id}
          tailoring={tailoring}
          setTailoring={setTailoring}
          onTicked={setTicked}
          onChanged={onRescore}
        />

        <Skills title="Required" skills={required} />
        <Skills title="Nice to have" skills={niceToHave} />
      </div>
      <footer className="foot">
        <button
          type="button"
          className="btn"
          onClick={() => void ask({ type: 'open-dashboard', path: '/app/applications' })}
        >
          Open dashboard
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={tracking === 'saving' || tracking === 'done'}
          onClick={() => void track()}
        >
          {tracking === 'saving' ? <Spinner /> : null}
          {tracking === 'done'
            ? 'Tracked'
            : tracking === 'saving'
              ? 'Saving…'
              : tracking === 'failed'
                ? 'Try again'
                : 'Track this job'}
        </button>
      </footer>
    </>
  );
}

/**
 * The job's own words (its title and skills) checked against the user's
 * resume. Anything missing can be ticked, and one button returns a copy of the
 * resume with those words changed, in the same style.
 */
function ResumeMatcher({
  matchId,
  tailoring,
  setTailoring,
  onTicked,
  onChanged,
}: {
  matchId: string;
  tailoring: Tailoring;
  setTailoring: (next: Tailoring) => void;
  /** Told which skills are ticked, so the score above can show where it would land. */
  onTicked: (skills: string[]) => void;
  onChanged: () => void;
}) {
  const [keywords, setKeywords] = useState<Keywords>({ name: 'loading' });
  const [skills, setSkills] = useState<string[]>([]);
  useEffect(() => onTicked(skills), [skills, onTicked]);
  const [respell, setRespell] = useState<string[]>([]);
  const [useHeadline, setUseHeadline] = useState(false);
  const [headline, setHeadline] = useState('');
  // Bumped when the saved resume changes, so the comparison is made again.
  const [resumeVersion, setResumeVersion] = useState(0);

  useEffect(() => {
    let current = true;
    setKeywords({ name: 'loading' });
    setSkills([]);
    setRespell([]);
    setUseHeadline(false);
    void ask({ type: 'keyword-check', matchId }).then((result) => {
      if (!current) return;
      if (!result.ok) {
        return setKeywords({
          name: 'failed',
          message: result.message,
          noResume: result.status === 404,
        });
      }
      setKeywords({ name: 'ready', check: result.data });
      setHeadline(result.data.title?.suggested ?? '');
    });
    return () => {
      current = false;
    };
  }, [matchId, resumeVersion]);

  // Where the progress and the finished resume appear. The button that starts
  // an update sits further down, so this is scrolled into view each time:
  // otherwise the result arrives above the part of the panel being looked at.
  const resultTop = useRef<HTMLDivElement>(null);
  const showing = tailoring.name === 'working' || tailoring.name === 'done';
  useEffect(() => {
    if (!showing) return;
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    resultTop.current?.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' });
  }, [showing, tailoring]);

  const resumeBlock =
    tailoring.name === 'working' ? (
      <UpdateProgress />
    ) : tailoring.name === 'done' ? (
      <TailoredCard
        tailored={tailoring.result}
        changes={tailoring.changes}
        onSaved={() => {
          // The resume and profile now include these changes: compare and score again.
          setResumeVersion((version) => version + 1);
          onChanged();
        }}
        onClose={() => setTailoring({ name: 'idle' })}
      />
    ) : null;
  const card = (
    <>
      <div ref={resultTop} className="anchor" />
      {resumeBlock}
    </>
  );
  // Once a copy exists, the checklist below is for changing it further.
  const heading = tailoring.name === 'done' ? 'Change something else' : 'Match your resume to this job';

  if (keywords.name === 'loading') {
    return (
      <>
        {card}
        <h3>{heading}</h3>
        <p className="muted small">Comparing this job with your resume…</p>
      </>
    );
  }
  if (keywords.name === 'failed') {
    return (
      <>
        {card}
        <h3>{heading}</h3>
        <p className="muted small hint">{keywords.message}</p>
        {keywords.noResume ? (
          <button
            type="button"
            className="btn wide"
            onClick={() => void ask({ type: 'open-dashboard', path: '/app/profile' })}
          >
            Upload my resume
          </button>
        ) : null}
      </>
    );
  }

  const { title, skills: all } = keywords.check;
  const missing = all.filter((skill) => skill.status === 'missing');
  const respellable = all.filter((skill) => skill.status === 'different_spelling');
  const canRetitle = !!title && !title.present && !!title.current && !!title.suggested;
  const headlineChosen = canRetitle && useHeadline && headline.trim().length >= 3;
  const count = skills.length + respell.length + (headlineChosen ? 1 : 0);

  async function update() {
    const changes: TailorRequest = {
      skills: skills.map((name) => ({ name, row: null })),
      respell: respellable
        .filter((skill) => respell.includes(skill.name))
        .map((skill) => ({ written_as: skill.written_as ?? skill.name, wanted: skill.name })),
      headline: headlineChosen ? headline.trim() : null,
    };
    setTailoring({ name: 'working' });
    const result = await ask({ type: 'tailor-resume', changes });
    if (!result.ok) return setTailoring({ name: 'failed', message: result.message });
    // A preview only: the saved resume, the profile and the score are unchanged
    // until the user saves it.
    setTailoring({ name: 'done', result: result.data, changes });
  }

  if (missing.length === 0 && respellable.length === 0 && !canRetitle) {
    return (
      <>
        {card}
        <h3>{heading}</h3>
        <p className="muted small">
          {title?.present
            ? `Your resume already uses this job's wording, including the title “${title.wanted}”.`
            : title && title.current === null
              ? `Your resume has the job's skills. It has no role line under your name for the title “${title.wanted}”.`
              : title
                ? `Your resume has the job's skills. “${title.wanted}” is a different kind of role from your “${title.current}”, so no title change is suggested.`
                : "Your resume already uses this job's wording."}
        </p>
      </>
    );
  }

  return (
    <>
      {card}
      <h3>{heading}</h3>
      <p className="muted small hint">
        {tailoring.name === 'done'
          ? 'Tick more or untick some, then update again. You get a fresh copy with everything ticked.'
          : 'Tick what to change. You get a copy in the same style.'}
      </p>

      {canRetitle && title ? (
        <div className="retitle">
          <label>
            <input
              type="checkbox"
              checked={useHeadline}
              onChange={(event) => setUseHeadline(event.target.checked)}
            />
            <span>Job title: change “{title.current}” under my name to</span>
          </label>
          <input
            type="text"
            aria-label="New headline"
            value={headline}
            maxLength={80}
            disabled={!useHeadline}
            // Job sites bind single-key shortcuts; typing here must not trigger them.
            onKeyDown={(event) => event.stopPropagation()}
            onChange={(event) => setHeadline(event.target.value)}
          />
        </div>
      ) : title ? (
        // Always say where the title stands, so a missing option is explained.
        <p className="muted small titlenote">
          {title.present
            ? `✓ Job title: your resume already says “${title.wanted}”.`
            : title.current === null
              ? `Job title: “${title.wanted}”. Your resume has no role line under your name to put it in.`
              : `Job title: “${title.wanted}” is a different kind of role from your “${title.current}”, so no change is suggested.`}
        </p>
      ) : null}

      {missing.length > 0 ? (
        <>
          <p className="group">Not in your resume (tick only what you really have)</p>
          <ul className="gaps">
            {missing.map((skill) => {
              const on = skills.includes(skill.name);
              return (
                <li key={skill.name}>
                  <button
                    type="button"
                    className={on ? 'chip on' : 'chip'}
                    aria-pressed={on}
                    onClick={() => setSkills(toggled(skills, skill.name))}
                  >
                    {on ? '✓' : '+'} {skill.name}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {respellable.length > 0 ? (
        <>
          <p className="group">Written differently from the job</p>
          <ul className="gaps">
            {respellable.map((skill) => {
              const on = respell.includes(skill.name);
              return (
                <li key={skill.name}>
                  <button
                    type="button"
                    className={on ? 'chip on' : 'chip'}
                    aria-pressed={on}
                    onClick={() => setRespell(toggled(respell, skill.name))}
                  >
                    {on ? '✓ ' : ''}
                    {skill.written_as} → {skill.name}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {count > 0 || tailoring.name === 'working' ? (
        <button
          type="button"
          className="btn primary wide"
          disabled={tailoring.name === 'working'}
          onClick={() => void update()}
        >
          {tailoring.name === 'working' ? <Spinner /> : null}
          {tailoring.name === 'working'
            ? 'Updating your resume…'
            : `${tailoring.name === 'done' ? 'Update again' : 'Update my resume'} (${count} ${count === 1 ? 'change' : 'changes'})`}
        </button>
      ) : null}
      {tailoring.name === 'failed' ? (
        <p className="problem" role="alert">
          {tailoring.message}
        </p>
      ) : null}
    </>
  );
}

type Keeping =
  | { name: 'idle' }
  | { name: 'asking' }
  | { name: 'saving' }
  | { name: 'saved' }
  | { name: 'failed'; message: string };

/**
 * Shown while the resume is being updated. The server does this in one step
 * and reports nothing along the way, so the bar is an estimate from how long
 * the work usually takes: quick at first, slowing down, and never reaching the
 * end until the result is really in.
 */
function UpdateProgress() {
  const [percent, setPercent] = useState(5);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => {
      const seconds = (Date.now() - started) / 1000;
      setPercent(Math.min(95, Math.round(5 + 90 * (1 - Math.exp(-seconds / 2.2)))));
    }, 150);
    return () => clearInterval(timer);
  }, []);
  const step =
    percent < 35
      ? 'Reading your resume'
      : percent < 65
        ? 'Making your changes'
        : percent < 88
          ? 'Checking a job site can still read it'
          : 'Preparing the preview';

  return (
    <section className="tailored" aria-live="polite">
      <strong>Updating your resume</strong>
      <div
        className="bar"
        role="progressbar"
        aria-label="Updating your resume"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <p className="muted small">
        {step}… {percent}%
      </p>
    </section>
  );
}

function openImage(base64: string) {
  const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
  window.open(url, '_blank', 'noopener');
  // Long enough for the new tab to load it.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function TailoredCard({
  tailored,
  changes,
  onSaved,
  onClose,
}: {
  tailored: Tailored;
  changes: TailorRequest;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [keeping, setKeeping] = useState<Keeping>({ name: 'idle' });
  const [view, setView] = useState<'after' | 'before'>('after');
  const count = tailored.added.length + tailored.changes.filter((change) => change.applied).length;
  const pages = view === 'after' ? tailored.after : tailored.before;
  const page = pages[0];

  async function save() {
    setKeeping({ name: 'saving' });
    const result = await ask({ type: 'keep-resume', changes });
    if (!result.ok) return setKeeping({ name: 'failed', message: result.message });
    setKeeping({ name: 'saved' });
    onSaved();
  }

  return (
    <section className="tailored done" aria-label="Your updated resume">
      <button type="button" className="icon close" aria-label="Dismiss" onClick={onClose}>
        ×
      </button>
      <strong className="ok">
        ✓ Your resume is updated ({count} {count === 1 ? 'change' : 'changes'})
      </strong>
      <p className="muted small">
        Look it over, then download it or save it. Nothing is kept until you do.
      </p>

      {/* The resume first: seeing it is how the user knows it really changed. */}
      <div className="tabs" role="tablist" aria-label="Which version to show">
        {(['after', 'before'] as const).map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={view === option}
            className={view === option ? 'tab on' : 'tab'}
            onClick={() => setView(option)}
          >
            {option === 'after' ? 'Updated' : 'Original'}
          </button>
        ))}
      </div>
      {page ? (
        <button
          type="button"
          className="previewbtn"
          title="Open full size in a new tab"
          onClick={() => openImage(page)}
        >
          <img
            className="preview"
            src={`data:image/png;base64,${page}`}
            alt={`${view === 'after' ? 'Updated' : 'Original'} resume, page 1`}
          />
          <span className="zoom">Open full size</span>
        </button>
      ) : null}
      {pages.length > 1 ? (
        <p className="muted small">Page 1 of {pages.length} is shown. The download has them all.</p>
      ) : null}

      <p className="group">What changed</p>
      <ul className="added">
        {tailored.changes.map((change) => (
          <li key={`${change.kind}-${change.after}`} className={change.applied ? '' : 'muted'}>
            {change.applied ? '✓ ' : '✕ '}
            {change.kind === 'headline' ? 'Headline: ' : 'Respelled: '}
            {change.before ? `${change.before} → ` : ''}
            <b>{change.after}</b>
            {change.applied ? null : ` was not changed. ${change.message ?? ''}`}
          </li>
        ))}
        {tailored.added.map((item) => (
          <li key={item.skill}>
            ✓ Added <b>{item.skill}</b>
            {item.row ? <span className="muted"> in {item.row}</span> : null}
            {item.exact_font ? null : <span className="muted"> (look-alike font, check it)</span>}
          </li>
        ))}
        {tailored.skipped.map((item) => (
          <li key={item.skill} className="muted">
            ✕ <b>{item.skill}</b> not added. {item.message}
          </li>
        ))}
      </ul>

      {/* Kept in view while the card is on screen, so the next step is never below the fold. */}
      <div className="actions">
        <button type="button" className="btn primary wide" onClick={() => downloadPdf(tailored)}>
          Download PDF
        </button>

        {keeping.name === 'saved' ? (
          <p className="saved" role="status">
            ✓ Saved as your resume. Every job check now counts these skills.
          </p>
        ) : keeping.name === 'asking' || keeping.name === 'saving' ? (
          <div className="confirm">
            <p className="small">
              Replace the resume saved in Rolesetu with this one? New skills are added to your
              profile too.
            </p>
            <div className="row">
              <button
                type="button"
                className="btn"
                disabled={keeping.name === 'saving'}
                onClick={() => setKeeping({ name: 'idle' })}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn primary"
                disabled={keeping.name === 'saving'}
                onClick={() => void save()}
              >
                {keeping.name === 'saving' ? <Spinner /> : null}
                {keeping.name === 'saving' ? 'Saving…' : 'Replace'}
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="btn wide" onClick={() => setKeeping({ name: 'asking' })}>
            Save as my resume
          </button>
        )}
      </div>
      {keeping.name === 'failed' ? (
        <p className="problem" role="alert">
          {keeping.message}
        </p>
      ) : null}

      <p className="muted small">
        Download it to use for this job only. Save it and these skills count in every job check
        from now on.
      </p>
    </section>
  );
}

function Skills({ title, skills }: { title: string; skills: SkillResult[] }) {
  if (skills.length === 0) return null;
  return (
    <>
      <h3>{title}</h3>
      <ul>
        {skills.map((skill) => {
          const verdict = VERDICT[skill.verdict];
          return (
            <li key={skill.name} className="skill">
              <div>
                <p className="name">{skill.name}</p>
                {skill.reason ? <p className="muted small">{skill.reason}</p> : null}
              </div>
              <span className="verdict">
                <i style={{ background: verdict.color }} />
                {verdict.label}
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function AutofillCard({
  state,
  onFill,
  onClose,
}: {
  state: Exclude<Autofill, { name: 'none' }>;
  onFill: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    if (state.name !== 'filled' && state.name !== 'failed') return;
    const timer = setTimeout(onClose, 9000);
    return () => clearTimeout(timer);
  }, [state.name, onClose]);

  const fields = (count: number) => `${count} ${count === 1 ? 'field' : 'fields'}`;

  return (
    <div className="notice autofill" role="status" aria-live="polite">
      {state.name === 'offer' ? (
        <>
          <strong>Fill this form from your profile?</strong>
          <span className="muted small">
            We can fill {fields(state.count)}. Nothing is sent: you check it and press Submit.
          </span>
          <div className="row">
            <button type="button" className="btn primary" onClick={onFill}>
              Autofill {fields(state.count)}
            </button>
          </div>
        </>
      ) : state.name === 'connect' ? (
        <>
          <strong>Autofill this form</strong>
          <span className="muted small">
            Connect Rolesetu to your account and we can fill this in from your profile.
          </span>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              onClick={() => void ask({ type: 'open-dashboard', path: '/app/settings' })}
            >
              Open Settings
            </button>
          </div>
        </>
      ) : state.name === 'filled' ? (
        <>
          <strong>Filled {fields(state.count)}</strong>
          <span className="muted small">
            They are outlined in blue. Check them, add anything missing, then submit it yourself.
          </span>
        </>
      ) : (
        <>
          <strong>Could not fill this form</strong>
          <span className="muted small">{state.message}</span>
        </>
      )}
      <button type="button" className="icon close" aria-label="Dismiss" onClick={onClose}>
        ×
      </button>
    </div>
  );
}

/** Sits inside a button while its action is running. The label beside it says what is happening. */
function Spinner() {
  return <span className="spin" aria-hidden />;
}

function NoticeCard({
  notice,
  saving,
  onYes,
  onNo,
  onClose,
}: {
  notice: Notice;
  /** The tracker is being updated after "Yes, I applied" or "Try again". */
  saving: boolean;
  onYes: (job: TrackedJob) => void;
  onNo: () => void;
  onClose: () => void;
}) {
  // A confirmation goes away by itself; a question or a failure waits for an answer.
  useEffect(() => {
    if (notice.kind !== 'applied') return;
    const timer = setTimeout(onClose, 9000);
    return () => clearTimeout(timer);
  }, [notice, onClose]);

  return (
    <div className="notice" role="status" aria-live="polite" aria-busy={saving}>
      {notice.kind === 'ask' ? (
        <>
          <strong>Did you apply for {notice.job.role}?</strong>
          <span className="muted small">
            We could not see the application from this page. It is saved either way.
          </span>
          <div className="row">
            <button type="button" className="btn" disabled={saving} onClick={onNo}>
              Not yet
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={saving}
              onClick={() => onYes(notice.job)}
            >
              {saving ? <Spinner /> : null}
              {saving ? 'Saving…' : 'Yes, I applied'}
            </button>
          </div>
        </>
      ) : notice.kind === 'applied' ? (
        <>
          <strong>Marked as applied</strong>
          <span className="muted small">
            {notice.job.role} at {notice.job.company} is in your applications.
          </span>
          <div className="row">
            <button
              type="button"
              className="btn"
              onClick={() => void ask({ type: 'open-dashboard', path: '/app/applications' })}
            >
              Open dashboard
            </button>
          </div>
        </>
      ) : (
        <>
          <strong>Could not update your tracker</strong>
          <span className="muted small">{notice.message}</span>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              disabled={saving}
              onClick={() => onYes(notice.job)}
            >
              {saving ? <Spinner /> : null}
              {saving ? 'Saving…' : 'Try again'}
            </button>
          </div>
        </>
      )}
      <button type="button" className="icon close" aria-label="Dismiss" onClick={onClose}>
        ×
      </button>
    </div>
  );
}
