/**
 * Turns the user's profile into values for a form and types them in. It only
 * fills empty fields, and it never clicks a button: sending the application
 * is always the user's own action.
 */

import type { AutofillData } from '../messages';
import { birthDateText } from './dates';
import { type Field, type Fillable, findFields } from './fields';
import { type WidgetField, comboboxIsEmpty, fillWidget, findWidgetFields } from './widgets';

type Profile = AutofillData['profile'];
type Job = Profile['experience'][number];

/** A field we have something for. `values` are tried in order (a dropdown may only offer one form). */
export type PlannedFill = { field: Field; values: string[] } | { widget: WidgetField; values: string[] };

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

function valuesFor(field: Field, data: AutofillData): string[] {
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
      return one(profile.links.portfolio);
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
      return one(answers[field.key]);
  }
}

function isEmpty(element: Fillable): boolean {
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
  const norm = (s: string) => s.trim().toLowerCase();

  for (const value of values) {
    const nv = norm(value);

    // 1. Exact match on option text or option value attribute.
    const exact = options.find((o) => norm(o.text) === nv || norm(o.value) === nv);
    if (exact) return exact;
  }

  // 2. Leading yes/no keyword.
  const lead = /^(yes|no)\b/i.exec(values[0] ?? '')?.[1]?.toLowerCase();
  if (lead) {
    const match = options.find((o) => norm(o.text).startsWith(lead));
    if (match) return match;
  }

  // 3. Substring / contains matching (saved answer appears inside option, or option inside answer).
  for (const value of values) {
    const nv = norm(value);
    if (nv.length < 3) continue; // too short — too many false positives
    const sub = options.find(
      (o) => norm(o.text).includes(nv) || nv.includes(norm(o.text)),
    );
    if (sub) return sub;
  }

  // 4. Synonym table.
  for (const value of values) {
    const nv = norm(value);
    const synonyms = ANSWER_SYNONYMS[nv] ?? [];
    const syn = options.find((o) => synonyms.some((s) => norm(o.text).includes(s)));
    if (syn) return syn;
    // Also check if the option's text maps to a synonym of our value.
    for (const [canonical, syns] of Object.entries(ANSWER_SYNONYMS)) {
      if (canonical === nv) continue;
      if (syns.some((s) => norm(value).includes(s))) {
        // Our value is a synonym of `canonical`; see if the option matches canonical.
        const match = options.find((o) => norm(o.text) === canonical || norm(o.text).startsWith(canonical.split(' ')[0] ?? ''));
        if (match) return match;
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
function type(element: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const limit = element.maxLength > 0 ? element.maxLength : value.length;
  const owner =
    element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(owner, 'value')?.set?.call(element, value.slice(0, limit));
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
}

function write(element: Fillable, values: string[]): boolean {
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
  type(element, value);
  return element.value !== '';
}

/** The empty fields on this page that the profile has a value for. */
export function planAutofill(doc: Document, data: AutofillData): PlannedFill[] {
  const plan: PlannedFill[] = [];

  // Native <input>, <textarea>, <select> fields.
  for (const field of findFields(doc)) {
    if (!isEmpty(field.element)) continue;
    const values = valuesFor(field, data);
    if (values.length === 0) continue;
    if (field.element instanceof HTMLSelectElement && !optionFor(field.element, values)) continue;
    plan.push({ field, values });
  }

  // Custom-widget dropdowns (SAP SuccessFactors / Capgemini, Workday, etc.)
  for (const widget of findWidgetFields(doc)) {
    if (!comboboxIsEmpty(widget.combobox)) continue;
    // Use saved_answers for the widget key (same key format as Field).
    const saved = data.saved_answers[widget.key];
    if (!saved) continue;
    plan.push({ widget, values: [saved] });
  }

  return plan;
}

function flash(element: HTMLElement): void {
  const before = element.style.outline;
  element.style.outline = '2px solid #2f5fe0';
  setTimeout(() => {
    element.style.outline = before;
  }, 2500);
}

/** Fills the planned fields and returns how many took the value. */
export function fill(plan: PlannedFill[]): number {
  let filled = 0;
  for (const item of plan) {
    if ('widget' in item) {
      // Custom widget field (SAP SuccessFactors / combobox pattern).
      if (!comboboxIsEmpty(item.widget.combobox)) continue; // already filled
      if (fillWidget(item.widget, item.values)) {
        flash(item.widget.combobox);
        filled += 1;
      }
    } else {
      const { field, values } = item;
      if (!field.element.isConnected || !isEmpty(field.element)) continue;
      if (!write(field.element, values)) continue;
      flash(field.element);
      filled += 1;
    }
  }
  return filled;
}
