/**
 * Autofill learns from the user's own typing. When they answer something we
 * had nothing for (a birth date, "How did you hear about us?"), the answer is
 * saved, and the next form that asks the same thing gets it filled in. An
 * answer they change is saved again, so the newest one is always used.
 */

import { parseBirthDate } from './dates';
import { type Field, findFields, hasApplicationForm, type Kind } from './fields';
import { formatHint } from './fill';

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

// Never kept, whatever is typed: identity numbers, money, and secrets.
const PRIVATE =
  /\bssn\b|social security|aadh?aa?r|\bpan\b|passport|national (?:id|insurance)|\btax\b|\btin\b|bank|account (?:no|number)|iban|ifsc|swift|routing|card|cvv|expiry|security (?:question|answer)|pass ?code|\bpin\b(?! ?code)|signature/;

const MAX_ANSWER = 500;
const SAVE_AFTER_MS = 800;

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

function isPrivate(field: Field): boolean {
  const { element } = field;
  const words = `${field.question ?? ''} ${field.label} ${element.getAttribute('name') ?? ''} ${element.id}`;
  return PRIVATE.test(words.toLowerCase());
}

/** The answer worth keeping from this field, or null. */
export function learnedAnswer(field: Field): string | null {
  const { element } = field;
  if (!LEARNED_KINDS.has(field.kind) || isPrivate(field)) return null;
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

export type Learned = { answer: LearnedAnswer; name: string };

/**
 * Watches the page for answers the user types or picks, and hands each batch
 * to `save` once they pause. `known` is what is saved already, so an answer
 * that is the same as before is not sent again; null means not connected.
 */
export function watchAnswers(
  doc: Document,
  known: () => Record<string, string> | null,
  save: (learned: Learned[]) => void,
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
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return;
    const saved = known();
    if (saved === null || !hasApplicationForm(doc)) return;
    const field = findFields(doc).find((candidate) => candidate.element === target);
    if (!field) return;
    const answer = learnedAnswer(field);
    if (answer === null || saved[field.key] === answer) return;

    queue.set(field.key, { answer: { question_key: field.key, answer }, name: answerName(field) });
    clearTimeout(timer);
    timer = setTimeout(flush, SAVE_AFTER_MS);
  };
  // The user may press Next or Submit before the pause is over.
  const onLeave = () => {
    if (doc.visibilityState === 'hidden') flush();
  };

  doc.addEventListener('change', onChange, true);
  doc.addEventListener('submit', flush, true);
  doc.addEventListener('visibilitychange', onLeave);
  window.addEventListener('pagehide', flush);
  return () => {
    flush();
    doc.removeEventListener('change', onChange, true);
    doc.removeEventListener('submit', flush, true);
    doc.removeEventListener('visibilitychange', onLeave);
    window.removeEventListener('pagehide', flush);
  };
}
