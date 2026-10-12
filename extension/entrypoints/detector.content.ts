import { hasApplicationForm } from '@/lib/autofill/fields';
import { ALL_SITES, DASHBOARD_MATCHES } from '@/lib/config';
import { detectJob } from '@/lib/job-detect';
import { ask } from '@/lib/messages';

const LOOK_AGAIN_MS = [1500, 4000];
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
      const found =
        hasApplicationForm(document) || detectJob(document, window.location.href, true) !== null;
      if (!found) return;
      asked = true;
      void ask({ type: 'activate' });
    };

    look();
    // Many pages draw the listing after they load.
    for (const delay of LOOK_AGAIN_MS) ctx.setTimeout(look, delay);
    // Sites that change page without reloading (LinkedIn, most job boards).
    ctx.addEventListener(window, 'wxt:locationchange', () => {
      look();
      for (const delay of LOOK_AGAIN_MS) ctx.setTimeout(look, delay);
    });
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
