/**
 * Autofill learns from the user's own typing and picking.
 *
 * Two-tier learning:
 *
 * 1. Server-side learned answers (`LEARNED_KINDS`): Sent to the backend and
 *    applied everywhere, across all sites. Used for things like notice period,
 *    CTC, work authorization, and any custom question that shows up on many
 *    career pages.
 *
 * 2. Site profile (local, per-hostname): Every trusted answer the user picks
 *    on a form — including dropdown selections — is saved instantly to
 *    `local:siteProfile:<hostname>`.  On the next visit to the same site, all
 *    those answers are merged in *before* the form is scanned, so the
 *    dropdowns are already filled without waiting for the server or asking the
 *    user to pick again.  This is what makes Capgemini (and every other career
 *    portal) feel instant on repeat visits.
 */

import { parseBirthDate } from './dates';
import { type Field, findFields, hasApplicationForm, type Kind } from './fields';
import { formatHint } from './fill';
import { watchWidgets } from './widgets';

export type LearnedAnswer = { question_key: string; answer: string };

// What the profile holds (name, jobs, schools...) is changed on the profile,
// never by a form. These are the questions that live in saved answers.
const LEARNED_KINDS: ReadonlySet<Kind> = new Set<Kind>([
  'notice_period',
  'current_ctc',
  'expected_ctc',
  'relocation',
  'work_authorization',
  'date_of_birth',
  'gender',
  'nationality',
  'postal_code',
  'heard_from',
  'question',
]);

/**
 * Kinds that are site-profile worthy even though they are not in LEARNED_KINDS.
 * A "why this role" essay is per-job, but a "why this role" *dropdown* (e.g.
 * "What is your employment type preference?") is a standing preference and
 * should be remembered for that site.
 */
const SITE_PROFILE_SELECT_KINDS: ReadonlySet<Kind> = new Set<Kind>([
  'why_this_role',
  'relocation',
  'work_authorization',
  'gender',
  'nationality',
  'heard_from',
  'notice_period',
  'question',
]);

// Never kept, whatever is typed: identity numbers, money, and secrets.
const PRIVATE =
  /\bssn\b|social security|aadh?aa?r|\bpan\b|passport|national (?:id|insurance)|\btax\b|\btin\b|bank|account (?:no|number)|iban|ifsc|swift|routing|card|cvv|expiry|security (?:question|answer)|pass ?(?:code|word)|\bpin\b(?! ?code)|signature/;
// Equal-opportunity and background questions stay on the form. They are not remembered.
const SENSITIVE =
  /\brace\b|ethnic|disabilit|veteran|religio|\bcaste\b|sexual orientation|criminal|convict|medical|health condition|pregnan|marital/;
const NOT_ANSWERS: ReadonlySet<string> = new Set(['password', 'hidden', 'file']);

const MAX_ANSWER = 500;
/** Debounce for text inputs — wait until the user pauses typing. */
const SAVE_AFTER_MS = 800;
/** No debounce for select picks — the change is already intentional. */
const SAVE_SELECT_AFTER_MS = 0;

const NAMES: Partial<Record<Kind, string>> = {
  notice_period: 'Notice period',
  current_ctc: 'Current CTC',
  expected_ctc: 'Expected CTC',
  relocation: 'Relocation',
  work_authorization: 'Work authorization',
  date_of_birth: 'Date of birth',
  gender: 'Gender',
  nationality: 'Nationality',
  postal_code: 'Postal code',
  heard_from: 'How you heard about the job',
};

/** What to call a field's answer when telling the user it was remembered. */
export function answerName(field: Field): string {
  const name = NAMES[field.kind] ?? field.question ?? field.key;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** Whether a raw question string matches the private/sensitive blocklists. */
export function isPrivateQuestion(question: string): boolean {
  const said = question.toLowerCase();
  return PRIVATE.test(said) || SENSITIVE.test(said);
}

function isPrivate(field: Field): boolean {
  const { element } = field;
  const words = `${field.question ?? ''} ${field.label} ${element.getAttribute('name') ?? ''} ${element.id}`;
  return isPrivateQuestion(words);
}

/** The answer worth keeping from this field for server-side learned answers, or null. */
export function learnedAnswer(field: Field): string | null {
  const { element } = field;
  if (!LEARNED_KINDS.has(field.kind) || isPrivate(field)) return null;
  if (element instanceof HTMLInputElement && NOT_ANSWERS.has(element.type)) return null;
  // Long answers are written for one job ("Why us?"), not reused.
  if (element instanceof HTMLTextAreaElement) return null;

  let value = element.value;
  if (element instanceof HTMLSelectElement) {
    // Still on its "Select..." placeholder: nothing was chosen.
    if (element.selectedIndex <= 0 || element.value === '') return null;
    // The words on the option travel between forms; its value ("opt_3") does not.
    value = element.selectedOptions[0]?.text ?? '';
  }
  const answer = value.replace(/\s+/g, ' ').trim();
  if (answer === '' || answer.length > MAX_ANSWER) return null;

  if (field.kind === 'date_of_birth') {
    return parseBirthDate(answer, formatHint(field), navigator.language);
  }
  return answer;
}

/**
 * The answer worth saving to the site profile for this field, or null.
 *
 * More permissive than `learnedAnswer`:
 *  - Also captures select picks for `SITE_PROFILE_SELECT_KINDS`.
 *  - Does NOT capture text inputs for non-learned kinds (those are per-job).
 *  - Captures the *visible option text* (travels to next visit), not the value.
 */
export function siteProfileAnswer(field: Field): string | null {
  const { element } = field;
  if (isPrivate(field)) return null;
  if (element instanceof HTMLInputElement && NOT_ANSWERS.has(element.type)) return null;
  if (element instanceof HTMLTextAreaElement) return null;

  if (element instanceof HTMLSelectElement) {
    if (element.selectedIndex <= 0 || element.value === '') return null;
    // Only save if this kind is worth remembering per site.
    if (!SITE_PROFILE_SELECT_KINDS.has(field.kind) && !LEARNED_KINDS.has(field.kind)) return null;
    const text = (element.selectedOptions[0]?.text ?? '').replace(/\s+/g, ' ').trim();
    return text === '' || text.length > MAX_ANSWER ? null : text;
  }

  // For text inputs: only save if it belongs to LEARNED_KINDS (these are
  // global preferences — e.g. "3 months" for notice period — and are equally
  // valid as site-profile answers).
  if (!LEARNED_KINDS.has(field.kind)) return null;
  const answer = element.value.replace(/\s+/g, ' ').trim();
  if (answer === '' || answer.length > MAX_ANSWER) return null;
  if (field.kind === 'date_of_birth') {
    return parseBirthDate(answer, formatHint(field), navigator.language);
  }
  return answer;
}

export type Learned = { answer: LearnedAnswer; name: string };

/**
 * Watches the page for answers the user types or picks, and hands each batch
 * to `save` once they pause. `known` is what is saved already, so an answer
 * that is the same as before is not sent again; null means not connected.
 *
 * `saveSite` is called immediately (no debounce) with each site-profile answer
 * — typically `(answers) => saveSiteProfile(hostname, answers)` wired in from
 * the caller that has access to the storage layer.  Passing `null` disables
 * site-profile recording (used in tests and when the storage layer is absent).
 *
 * Additionally, every accepted answer on a select field is saved immediately
 * to the local site profile so the next visit to this hostname gets it filled
 * in without any round-trip.
 */
export function watchAnswers(
  doc: Document,
  known: () => Record<string, string> | null,
  save: (learned: Learned[]) => void,
  saveSite: ((answers: Record<string, string>) => void) | null = null,
): () => void {
  const queue = new Map<string, Learned>();
  let timer: ReturnType<typeof setTimeout> | undefined;

  const flush = () => {
    clearTimeout(timer);
    if (queue.size === 0) return;
    const batch = [...queue.values()];
    queue.clear();
    save(batch);
  };

  const onChange = (event: Event) => {
    // Autofill's own writes fire `change` too; only what the user does is learned.
    if (!event.isTrusted) return;
    const target = event.target;
    if (
      !(
        target instanceof HTMLInputElement ||
        target instanceof HTMLSelectElement ||
        target instanceof HTMLTextAreaElement
      )
    )
      return;
    const saved = known();
    if (saved === null || !hasApplicationForm(doc)) return;
    const field = findFields(doc).find((candidate) => candidate.element === target);
    if (!field) return;

    // --- Site profile: save select picks immediately (no debounce needed). ---
    const spAnswer = siteProfileAnswer(field);
    if (spAnswer !== null && saveSite !== null) {
      saveSite({ [field.key]: spAnswer });
    }

    // --- Server-side learned answers (debounced). ---
    const answer = learnedAnswer(field);
    if (answer === null || saved[field.key] === answer) return;

    const isSelect = target instanceof HTMLSelectElement;
    queue.set(field.key, { answer: { question_key: field.key, answer }, name: answerName(field) });
    clearTimeout(timer);
    // Select picks are already final — flush immediately instead of waiting.
    timer = setTimeout(flush, isSelect ? SAVE_SELECT_AFTER_MS : SAVE_AFTER_MS);
  };

  // The user may press Next or Submit before the pause is over.
  const onLeave = () => {
    if (doc.visibilityState === 'hidden') flush();
  };

  doc.addEventListener('change', onChange, true);
  doc.addEventListener('submit', flush, true);
  doc.addEventListener('visibilitychange', onLeave);
  window.addEventListener('pagehide', flush);

  // Watch custom-widget dropdowns (SAP SuccessFactors, Workday, Greenhouse etc.)
  // These never fire a native trusted `change` on a <select>, so we watch the
  // combobox text directly via MutationObserver inside watchWidgets.
  const stopWidgets = watchWidgets(doc, (key, visibleText, kind, label) => {
    const saved = known();
    if (saved === null) return;

    // Save to site profile immediately (no debounce — a pick is always final).
    if (saveSite !== null) {
      saveSite({ [key]: visibleText });
    }

    // Also queue for server-side storage if this kind is learned server-side.
    if (LEARNED_KINDS.has(kind) && saved[key] !== visibleText) {
      queue.set(key, {
        answer: { question_key: key, answer: visibleText },
        name: label.charAt(0).toUpperCase() + label.slice(1, 40),
      });
      clearTimeout(timer);
      timer = setTimeout(flush, SAVE_SELECT_AFTER_MS);
    }
  });

  return () => {
    flush();
    stopWidgets();
    doc.removeEventListener('change', onChange, true);
    doc.removeEventListener('submit', flush, true);
    doc.removeEventListener('visibilitychange', onLeave);
    window.removeEventListener('pagehide', flush);
  };
}
