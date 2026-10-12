/**
 * Works out, from what happens on the page, whether the user applied.
 *
 * Three things can be seen from here:
 *  - the user pressed an Apply or Submit button;
 *  - the page then said the application went through;
 *  - the user left to apply elsewhere and came back.
 * Nothing is ever clicked or submitted for the user; this only watches.
 */

import { APPLY, CONTROLS, labelOf } from '@/lib/apply-controls';
import { whenSettled } from '@/lib/settled';

const SUBMIT = /^(?:submit|send)(?: (?:my |your |the )?application)?$|^submit$|^apply and submit$/i;
// What a site says once an application has gone through.
const SUCCESS =
  /application (?:was |has been |is )?(?:successfully )?(?:submitted|sent|received)|successfully applied|applied successfully|you(?:'ve| have) (?:successfully )?applied|thanks? (?:you )?for applying|your application (?:has been|was) (?:sent|submitted|received)/i;

/** How long after pressing Apply we keep expecting a confirmation. */
export const PENDING_FOR_MS = 45 * 60 * 1000;

/** Which kind of button a click landed on, if it was one that starts or sends an application. */
export function applyActionOf(target: EventTarget | null): 'apply' | 'submit' | null {
  if (!(target instanceof Element)) return null;
  // Our own score pill and panel are never the site's Apply button.
  if (target.closest('[data-rolesetu-pill], rolesetu-root')) return null;
  const control = target.closest(CONTROLS);
  if (!control) return null;
  const label = labelOf(control);
  if (label.length > 40) return null;
  if (APPLY.test(label)) return 'apply';
  if (SUBMIT.test(label)) return 'submit';
  return null;
}

export function pageConfirmsApplication(): boolean {
  return SUCCESS.test(document.body.innerText);
}

/**
 * Calls `onConfirmed` once, when the page starts saying the application went
 * through. Returns a function that stops watching.
 *
 * `ignoreExisting` is for a watch that begins on a click: a confirmation that
 * was already on the page before then belongs to something else.
 */
export function watchForConfirmation(onConfirmed: () => void, ignoreExisting: boolean): () => void {
  if (pageConfirmsApplication()) {
    if (!ignoreExisting) {
      onConfirmed();
      return () => {};
    }
    // Already showing a confirmation before the click: nothing new can be told apart.
    return () => {};
  }

  let done = false;
  const stop = () => {
    done = true;
    observer.disconnect();
    read.cancel();
    clearTimeout(giveUp);
  };
  // Reading the whole page's text is not free, so wait for it to settle.
  const read = whenSettled(
    () => {
      if (!done && pageConfirmsApplication()) {
        stop();
        onConfirmed();
      }
    },
    700,
    3000,
  );
  const observer = new MutationObserver(read);
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  const giveUp = setTimeout(stop, PENDING_FOR_MS);
  return stop;
}
