/**
 * Turns the user's profile into values for a form and types them in. It only
 * fills empty fields, and it never clicks a button: sending the application
 * is always the user's own action.
 */

import type { AutofillData } from '../messages';
import { birthDateText } from './dates';
import { type Field, type Fillable, findFields, isRadio, radioBox, radioGroup, radioText } from './fields';
import { type WidgetField, comboboxIsEmpty, fillWidget, findWidgetFields } from './widgets';

type Profile = AutofillData['profile'];
type Job = Profile['experience'][number];

/**
 * A field we have something for. `values` are tried in order (a dropdown may only
 * offer one form). `draft` is an answer the user gave to a question worded
 * differently: it is filled in, but marked for the user to check.
 */
export type PlannedFill = ({ field: Field } | { widget: WidgetField }) & { values: string[]; draft: boolean };

/**
 * An answer for a question no answer is saved under: the user's answer to a
 * similarly worded question, or one written for this company. `label` tells the
 * user where it came from; `draft` ones are marked for the user to check.
 */
export type Suggestion = {
  answer: string;
  label: string;
  draft: boolean;
  /** Made for this company: used even over an answer saved under the same words, which may name the last one. */
  preferred?: boolean;
  /** Where it came from, for analytics: a reworded question, the user's own answer, or the profile. */
  source: 'similar' | 'your_answer' | 'profile';
};
export type Suggestions = ReadonlyMap<string, Suggestion>;

/** The job being applied to, for answers saved with {company} and {role} in them. */
export type JobNames = { company: string | null; role: string | null };
const NO_NAMES: JobNames = { company: null, role: null };

/** A saved answer with this job's names in place of its tokens. */
export function fillTokens(text: string, names: JobNames): string {
  const role = names.role ?? 'open';
  return text
    // "a {role}" stays right for "an AI Engineer".
    .replace(/\b([Aa])n? \{role\}/g, (_, a: string) => `${/^[aeiou]/i.test(role) ? `${a}n` : a} {role}`)
    .replaceAll('{company}', names.company ?? 'your company')
    .replaceAll('{role}', names.role ?? 'open')
    .replaceAll('{founder}', 'there');
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * A written answer made reusable: this company's and role's names become
 * {company} and {role}, so the next company's names go in their place. Short
 * answers ("Yes", "30 days") are left as they are.
 */
export function asTemplate(text: string, names: JobNames): string {
  return templateParts(text, names).text;
}

// Endings a listing adds that a person leaves out when writing the name.
const LEGAL_ENDING =
  /\s+(?:private limited|pvt\.? ?ltd\.?|ltd\.?|limited|inc\.?|llc|llp|corp(?:oration)?\.?|co\.?|gmbh|technologies|technology|systems|solutions|software|labs|india)$/i;
// First words too common to stand for the company on their own ("Data" of "Data Axle").
const COMMON_FIRST =
  /^(?:the|team|global|digital|smart|data|tech|cloud|india|new|open|next|first|big|one|my|your|our|good|best|blue|red|green|united|national|international|people|life|health|ai)$/i;

/**
 * The ways an answer may write a company's name: as listed ("Finflock Systems
 * Private Limited"), without its legal ending ("Finflock"), and by its own first
 * word when that word is distinctive ("Loopr" of "Loopr AI"). Longest first.
 */
export function nameVariants(name: string): string[] {
  const variants = new Set<string>();
  let current = name.trim();
  variants.add(current);
  while (LEGAL_ENDING.test(current)) {
    current = current.replace(LEGAL_ENDING, '').trim();
    variants.add(current);
  }
  const words = current.split(/\s+/);
  const [first] = words;
  if (first && words.length > 1 && first.length >= 4 && !COMMON_FIRST.test(first)) variants.add(first);
  return [...variants].filter((variant) => variant.length >= 2).sort((a, b) => b.length - a.length);
}

/**
 * The answer with this job's names as tokens, and which names were swapped (to
 * tell the user). Short answers ("Yes", "30 days") are left as they are.
 */
export function templateParts(text: string, names: JobNames): { text: string; swapped: string[] } {
  if (text.length < 40) return { text, swapped: [] };
  let template = text;
  const swapped: string[] = [];
  for (const [name, token] of [
    [names.role, '{role}'],
    [names.company, '{company}'],
  ] as const) {
    if (!name || name.trim().length < 2) continue;
    for (const variant of token === '{company}' ? nameVariants(name) : [name.trim()]) {
      const pattern = new RegExp(`(?<![\\w])${escapeRegExp(variant)}(?![\\w])`, 'gi');
      if (!pattern.test(template)) continue;
      template = template.replace(pattern, token);
      swapped.push(variant);
    }
  }
  return { text: template, swapped };
}

// Questions whose answer lives in saved answers, so one given to a differently
// worded question can be reused. Profile fields (name, jobs...) come from the profile.
const REUSABLE_KINDS: ReadonlySet<Field['kind']> = new Set<Field['kind']>([
  'notice_period',
  'current_ctc',
  'expected_ctc',
  'relocation',
  'work_authorization',
  'why_this_role',
  'heard_from',
  'question',
]);

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/**
 * Synonyms for common answers that appear under many surface forms in dropdowns.
 * Used as a last-resort fallback in `optionFor` when exact and leading-word
 * matching both fail.  The key is what we have in `saved_answers`; the values
 * are alternative texts the dropdown option might use.
 */
const ANSWER_SYNONYMS: Record<string, string[]> = {
  yes: ['i agree', 'agree', 'i accept', 'accept', 'i consent', 'consent', 'i do', 'affirmative'],
  no: ['i do not agree', 'disagree', 'decline', 'i decline', 'i do not consent', 'i do not', 'negative'],
  'no selection': [],
  // Work authorization variants
  'yes, i am authorized': ['yes – i am authorized', 'authorized', 'i am authorized to work'],
  'no, i am not authorized': ['not authorized', 'i am not authorized'],
  // Relocation
  'yes, willing to relocate': ['willing to relocate', 'open to relocation', 'yes – willing'],
  'not willing to relocate': ['not open to relocation', 'no – not willing'],
};

/** Most recent job first: the one still held, then by when each ended. */
function newestFirst(jobs: Job[]): Job[] {
  const key = (job: Job) => `${job.end ?? '9999-12'}${job.start ?? ''}`;
  return [...jobs].sort((a, b) => key(b).localeCompare(key(a)));
}

function dateValues(yearMonth: string | null | undefined, element: Fillable, label: string): string[] {
  if (!yearMonth) return [];
  const [year = '', month = ''] = yearMonth.split('-');
  const name = MONTHS[Number(month) - 1] ?? '';
  if (element instanceof HTMLInputElement && element.type === 'date') return [`${yearMonth}-01`];
  if (element instanceof HTMLInputElement && element.type === 'month') return [yearMonth];
  if (/year/.test(label) && !/month/.test(label)) return [year];
  if (/month/.test(label) && !/year/.test(label)) return [name, name.slice(0, 3), month, String(Number(month))];
  if (element instanceof HTMLSelectElement) return [year, name, name.slice(0, 3)];
  return [`${month}/${year}`];
}

/** The words the form shows beside a field, as written, for reading a date format from. */
export function formatHint(field: Field): string {
  return `${field.element.getAttribute('placeholder') ?? ''} ${field.label}`;
}

function yearsText(years: number): string {
  if (years <= 0) return '';
  return years >= 1 ? String(Math.round(years)) : years.toFixed(1);
}

function valuesFor(field: Field, data: AutofillData, applyingTo: JobNames = NO_NAMES): string[] {
  const { profile, saved_answers: answers } = data;
  const names = (profile.full_name ?? '').split(/\s+/).filter(Boolean);
  const job = newestFirst(profile.experience)[field.entry];
  const school = profile.education[field.entry];
  const one = (value: string | number | null | undefined) =>
    value === null || value === undefined || value === '' ? [] : [String(value)];

  switch (field.kind) {
    case 'first_name':
      return one(names[0]);
    case 'last_name':
      return one(names.slice(1).join(' '));
    case 'full_name':
      return one(profile.full_name);
    case 'email':
      return one(data.email);
    case 'phone':
      return one(profile.phone);
    case 'location':
      return one(profile.location);
    case 'linkedin':
      return one(profile.links.linkedin);
    case 'github':
      return one(profile.links.github);
    case 'portfolio':
      // "Share a link to your work samples": a portfolio, else the code itself.
      return [...one(profile.links.portfolio), ...one(profile.links.github)];
    case 'headline':
      return one(profile.headline);
    case 'years':
      return one(yearsText(data.years_of_experience));
    case 'skills':
      return one(profile.skills.map((skill) => skill.name).join(', '));
    case 'company':
      return one(job?.company);
    case 'title':
      return one(job?.title);
    case 'job_description':
      return one(job?.description);
    case 'job_start':
      return dateValues(job?.start, field.element, field.label);
    case 'job_end':
      return dateValues(job?.end, field.element, field.label);
    case 'school':
      return one(school?.school);
    case 'degree':
      return one(school?.degree);
    case 'field':
      return one(school?.field);
    case 'edu_start':
      return one(school?.start_year);
    case 'edu_end':
      return one(school?.end_year);
    case 'date_of_birth': {
      const saved = answers[field.key];
      const type = field.element instanceof HTMLInputElement ? field.element.type : '';
      // An answer saved some other way (typed in on the dashboard) is used as it is.
      return one(saved && (birthDateText(saved, formatHint(field), navigator.language, type) ?? saved));
    }
    default:
      // Saved answers, including every one learned from an earlier form.
      const saved = answers[field.key];
      return one(saved && fillTokens(saved, applyingTo));
  }
}

function isEmpty(element: Fillable): boolean {
  if (isRadio(element)) return !radioGroup(element).some((radio) => radio.checked);
  if (element instanceof HTMLSelectElement) {
    const chosen = element.selectedOptions[0];
    // A dropdown still on its "Select..." placeholder counts as empty.
    return !chosen || chosen.value === '' || element.selectedIndex === 0;
  }
  return element.value.trim() === '';
}

/**
 * Finds the best matching option for a set of candidate values.
 *
 * Matching priority (first win):
 *  1. Exact text or value match (case-insensitive, trimmed).
 *  2. Leading "Yes"/"No" word — e.g. saved "Yes" matches "Yes, within India".
 *  3. The saved value is contained inside the option text, or vice-versa.
 *     e.g. saved "Authorized" matches option "Yes, I am authorized to work".
 *  4. Synonym table — common consent/authorization phrasing variants.
 */
export function optionFor(select: HTMLSelectElement, values: string[]): HTMLOptionElement | null {
  const options = [...select.options].filter((option) => !option.disabled && option.value !== '');
  return bestChoice(
    options.map((option) => ({ item: option, text: option.text, value: option.value })),
    values,
  );
}

/** The radio option that best matches the saved answer, by the words beside it. */
export function radioFor(radio: HTMLInputElement, values: string[]): HTMLInputElement | null {
  const options = radioGroup(radio).filter((option) => !option.disabled);
  return bestChoice(
    options.map((option) => ({ item: option, text: radioText(option), value: option.value })),
    values,
  );
}

type Choice<T> = { item: T; text: string; value: string };

function bestChoice<T>(choices: Choice<T>[], values: string[]): T | null {
  const norm = (s: string) => s.trim().toLowerCase();

  for (const value of values) {
    const nv = norm(value);

    // 1. Exact match on option text or option value attribute.
    const exact = choices.find((o) => norm(o.text) === nv || norm(o.value) === nv);
    if (exact) return exact.item;
  }

  // 2. Leading yes/no keyword.
  const lead = /^(yes|no)\b/i.exec(values[0] ?? '')?.[1]?.toLowerCase();
  if (lead) {
    const match = choices.find((o) => new RegExp(`^${lead}\\b`).test(norm(o.text)));
    if (match) return match.item;
  }

  // 3. Substring / contains matching (saved answer appears inside option, or option inside answer).
  for (const value of values) {
    const nv = norm(value);
    if (nv.length < 3) continue; // too short — too many false positives
    const sub = choices.find((o) => norm(o.text).includes(nv) || (norm(o.text).length >= 3 && nv.includes(norm(o.text))));
    if (sub) return sub.item;
  }

  // 4. Synonym table.
  for (const value of values) {
    const nv = norm(value);
    const synonyms = ANSWER_SYNONYMS[nv] ?? [];
    const syn = choices.find((o) => synonyms.some((s) => norm(o.text).includes(s)));
    if (syn) return syn.item;
    // Also check if the option's text maps to a synonym of our value.
    for (const [canonical, syns] of Object.entries(ANSWER_SYNONYMS)) {
      if (canonical === nv) continue;
      if (syns.some((s) => nv.includes(s))) {
        // Our value is a synonym of `canonical`; see if the option matches canonical.
        const match = choices.find(
          (o) => norm(o.text) === canonical || norm(o.text).startsWith(canonical.split(' ')[0] ?? ''),
        );
        if (match) return match.item;
      }
    }
  }

  return null;
}

/**
 * Sets a value the way typing does. Sites built with React keep their own copy
 * of each field and ignore a plain `element.value = ...`; going through the
 * browser's own setter and then firing the events makes them notice.
 */
export function setText(element: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const limit = element.maxLength > 0 ? element.maxLength : value.length;
  const owner =
    element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(owner, 'value')?.set?.call(element, value.slice(0, limit));
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
}

function write(element: Fillable, values: string[]): boolean {
  if (isRadio(element)) {
    const option = radioFor(element, values);
    if (!option) return false;
    // A click, not `checked = true`: sites built with React only notice a click.
    option.click();
    return option.checked;
  }
  if (element instanceof HTMLSelectElement) {
    const option = optionFor(element, values);
    if (!option) return false;
    element.value = option.value;
    element.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }
  const value = values[0];
  if (value === undefined) return false;
  if (element instanceof HTMLInputElement && element.type === 'number' && Number.isNaN(Number(value))) {
    return false;
  }
  setText(element, value);
  return element.value !== '';
}

/** A question on the page with no answer stored under its key: worth asking the server about. */
export type UnansweredQuestion = { key: string; text: string };

/**
 * The empty questions on this page that no saved answer is stored under, with
 * the words a person reads beside them. The server may have an answer the user
 * gave to the same question worded differently.
 */
export function unansweredQuestions(doc: Document, data: AutofillData): UnansweredQuestion[] {
  const found = new Map<string, string>();
  for (const field of findFields(doc)) {
    if (!REUSABLE_KINDS.has(field.kind) || !isEmpty(field.element)) continue;
    if (valuesFor(field, data).length > 0) continue;
    const text = field.question ?? field.label;
    if (text.length >= 4) found.set(field.key, text.slice(0, 500));
  }
  for (const widget of findWidgetFields(doc)) {
    if (!comboboxIsEmpty(widget.combobox) || data.saved_answers[widget.key]) continue;
    if (widget.label.length >= 4) found.set(widget.key, widget.label.slice(0, 500));
  }
  return [...found].map(([key, text]) => ({ key, text }));
}

/**
 * The words around a box whose own label says little: the heading and opening
 * lines of the pop-up or section it sits in ("Reach out to the team at Encord.
 * Share something about you...").
 */
export function contextOf(element: Element): string {
  let box = element.closest('[role="dialog"], dialog, [aria-modal="true"]');
  for (let up = element.parentElement, depth = 0; !box && up && depth < 8; up = up.parentElement, depth += 1) {
    if (up.querySelector('h1, h2, h3, [role="heading"]')) box = up;
  }
  if (!box) return '';
  const heading = box.querySelector('h1, h2, h3, [role="heading"]')?.textContent ?? '';
  const intro = [...box.querySelectorAll('p')]
    .slice(0, 2)
    .map((paragraph) => paragraph.textContent ?? '');
  return [heading, ...intro]
    .map((text) => text.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join('. ')
    .slice(0, 1000);
}

/** A written question on the page, with the words around it. */
export type WrittenQuestion = { key: string; text: string; context: string };

/**
 * The empty written-answer boxes on this page ("Why this company?", a message to
 * the team), asked about even when an answer is saved under the same words: the
 * same "Your message" box is on every company's page, so what was saved names the
 * last company.
 */
export function writtenQuestions(doc: Document): WrittenQuestion[] {
  const found = new Map<string, WrittenQuestion>();
  for (const field of findFields(doc)) {
    const written = field.element instanceof HTMLTextAreaElement || field.kind === 'why_this_role';
    if (!written || !REUSABLE_KINDS.has(field.kind) || !isEmpty(field.element)) continue;
    const text = (field.question ?? field.label).slice(0, 500);
    if (text.length < 2) continue;
    found.set(field.key, { key: field.key, text, context: contextOf(field.element) });
  }
  return [...found.values()].slice(0, 10);
}

/** The empty fields on this page that the profile, or an answer to a similar question, has a value for. */
export function planAutofill(
  doc: Document,
  data: AutofillData,
  suggestions: Suggestions = new Map(),
  names: JobNames = NO_NAMES,
): PlannedFill[] {
  const plan: PlannedFill[] = [];

  // Native <input>, <textarea>, <select> fields.
  for (const field of findFields(doc)) {
    if (!isEmpty(field.element)) continue;
    let values = valuesFor(field, data, names);
    let draft = false;
    const suggested = suggestions.get(field.key);
    if (suggested?.preferred && REUSABLE_KINDS.has(field.kind)) {
      values = [suggested.answer];
      draft = true;
    } else if (values.length === 0 && suggested && REUSABLE_KINDS.has(field.kind)) {
      values = [suggested.answer];
      draft = suggested.draft;
    }
    if (values.length === 0) continue;
    if (field.element instanceof HTMLSelectElement && !optionFor(field.element, values)) continue;
    if (isRadio(field.element) && !radioFor(field.element, values)) continue;
    plan.push({ field, values, draft });
  }

  // Custom-widget dropdowns (SAP SuccessFactors / Capgemini, Workday, etc.)
  for (const widget of findWidgetFields(doc)) {
    if (!comboboxIsEmpty(widget.combobox)) continue;
    // Use saved_answers for the widget key (same key format as Field).
    const saved = data.saved_answers[widget.key];
    const suggested = suggestions.get(widget.key);
    if (saved) plan.push({ widget, values: [fillTokens(saved, names)], draft: false });
    else if (suggested) plan.push({ widget, values: [suggested.answer], draft: suggested.draft });
  }

  return plan;
}

const FILLED_OUTLINE = '2px solid #2f5fe0';
// Amber: an answer given to a similar question. It stays until the user edits the field.
const DRAFT_OUTLINE = '2px dashed #d97706';

function flash(element: HTMLElement): void {
  const before = element.style.outline;
  element.style.outline = FILLED_OUTLINE;
  setTimeout(() => {
    element.style.outline = before;
  }, 2500);
}

export function markDraft(element: HTMLElement): void {
  const before = element.style.outline;
  element.style.outline = DRAFT_OUTLINE;
  const clear = (event: Event) => {
    if (!event.isTrusted) return;
    element.style.outline = before;
    element.removeEventListener('input', clear);
    element.removeEventListener('change', clear);
  };
  element.addEventListener('input', clear);
  element.addEventListener('change', clear);
}

export type FillResult = { filled: number; drafts: number };

/** Fills the planned fields and counts how many took the value, and how many of those are drafts to check. */
export function fill(plan: PlannedFill[]): FillResult {
  const result: FillResult = { filled: 0, drafts: 0 };
  for (const item of plan) {
    let element: HTMLElement;
    if ('widget' in item) {
      // Custom widget field (SAP SuccessFactors / combobox pattern).
      if (!comboboxIsEmpty(item.widget.combobox)) continue; // already filled
      if (!fillWidget(item.widget, item.values)) continue;
      element = item.widget.combobox;
    } else {
      const { field, values } = item;
      if (!field.element.isConnected || !isEmpty(field.element)) continue;
      if (!write(field.element, values)) continue;
      element = isRadio(field.element) ? radioBox(field.element) : field.element;
    }
    result.filled += 1;
    if (item.draft) {
      result.drafts += 1;
      markDraft(element);
    } else {
      flash(element);
    }
  }
  return result;
}
