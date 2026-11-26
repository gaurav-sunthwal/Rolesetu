import { hasApplicationForm } from '@/lib/autofill/fields';
import { ALL_SITES, DASHBOARD_MATCHES } from '@/lib/config';
import { detectJob } from '@/lib/job-detect';
import { ask } from '@/lib/messages';

const LOOK_AGAIN_MS = [1500, 4000];
const AFTER_CLICK_MS = [800, 2500];
const MIN_FRAME = { width: 320, height: 240 };

/**
 * The only part that runs on every page, so it is kept small: it decides
 * whether the page is a job listing or an application form and, if so, asks
 * the background worker to load the real UI. On any other page it does
 * nothing and sends nothing.
 */
export default defineContentScript({
  matches: ALL_SITES,
  excludeMatches: DASHBOARD_MATCHES,
  allFrames: true, // application forms are often embedded in a frame
  runAt: 'document_idle',
  main(ctx) {
    const inFrame = window !== window.top;
    // Ad and tracking frames are never job pages.
    if (inFrame && (window.innerWidth < MIN_FRAME.width || window.innerHeight < MIN_FRAME.height)) {
      return;
    }

    let asked = false;
    const look = () => {
      if (asked || ctx.isInvalid || window.__rolesetuMounted) return;
      const form = hasApplicationForm(document);
      const found = form ? 'form' : detectJob(document, window.location.href, true) !== null ? 'job' : null;
      if (!found) return;
      asked = true;
      // A form is filled where it is, so the UI goes into its frame. A job inside an
      // embedded job board is shown on the page around it, which reads it from here.
      void ask({ type: 'activate', found, frame: found === 'job' && inFrame ? 'top' : undefined });
    };

    // The page around an embedded job board asks its frames for the job on show, and an
    // application form embedded in a frame asks the page around it ("Write with AI" needs
    // the company and role). Only a frame with a job answers, so the first answer is the job.
    browser.runtime.onMessage.addListener((message: unknown) => {
      const asking = message as { type?: unknown; strict?: unknown } | null;
      if (asking?.type !== 'read-job') return undefined;
      const job = detectJob(document, window.location.href, asking.strict === true);
      return job ? Promise.resolve(job) : undefined;
    });

    look();
    // Many pages draw the listing after they load.
    for (const delay of LOOK_AGAIN_MS) ctx.setTimeout(look, delay);
    // Sites that change page without reloading (LinkedIn, most job boards).
    ctx.addEventListener(window, 'wxt:locationchange', () => {
      look();
      for (const delay of LOOK_AGAIN_MS) ctx.setTimeout(look, delay);
    });
    // A job opened in a pop-up (Internshala opens most jobs this way) changes
    // neither the address nor anything else watched here, so a click is the sign.
    let lastClickLook = 0;
    ctx.addEventListener(
      document,
      'click',
      () => {
        if (asked || Date.now() - lastClickLook < 1000) return;
        lastClickLook = Date.now();
        for (const delay of AFTER_CLICK_MS) ctx.setTimeout(look, delay);
      },
      { capture: true, passive: true },
    );
    // A form opened later (an "Apply" pop-up) is caught when the user steps into it.
    let lastFocusLook = 0;
    ctx.addEventListener(document, 'focusin', (event) => {
      if (asked || Date.now() - lastFocusLook < 2000) return;
      if (!(event.target instanceof Element) || !event.target.matches('input, textarea, select')) return;
      lastFocusLook = Date.now();
      look();
    });
  },
});
