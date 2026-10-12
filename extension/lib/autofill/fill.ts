/**
 * Turns the user's profile into values for a form and types them in. It only
 * fills empty fields, and it never clicks a button: sending the application
 * is always the user's own action.
 */

import type { AutofillData } from '../messages';
import { type Field, type Fillable, findFields } from './fields';

type Profile = AutofillData['profile'];
type Job = Profile['experience'][number];

/** A field we have something for. `values` are tried in order (a dropdown may only offer one form). */
export type PlannedFill = { field: Field; values: string[] };

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

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
    default:
      return one(answers[field.kind]);
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

function optionFor(select: HTMLSelectElement, values: string[]): HTMLOptionElement | null {
  const options = [...select.options].filter((option) => !option.disabled && option.value !== '');
  const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();
  for (const value of values) {
    const exact = options.find((option) => same(option.text, value) || same(option.value, value));
    if (exact) return exact;
  }
  // "Yes, within India" should still pick a plain "Yes".
  const lead = /^(yes|no)\b/i.exec(values[0] ?? '')?.[1];
  return (lead && options.find((option) => same(option.text, lead))) || null;
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
  for (const field of findFields(doc)) {
    if (!isEmpty(field.element)) continue; // what the user typed is never replaced
    const values = valuesFor(field, data);
    if (values.length === 0) continue;
    if (field.element instanceof HTMLSelectElement && !optionFor(field.element, values)) continue;
    plan.push({ field, values });
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
  for (const { field, values } of plan) {
    if (!field.element.isConnected || !isEmpty(field.element)) continue;
    if (!write(field.element, values)) continue;
    flash(field.element);
    filled += 1;
  }
  return filled;
}
