/**
 * Which boxes "Write with AI" is offered on: any box that asks for words, never
 * one that asks for a fact only the user knows (a salary, a date, a link).
 * No DOM in here, so it is tested on its own.
 */
import type { Kind } from './fields';

/** The box as far as this rule cares: a <textarea>, or an <input> of some type. */
export type Box = { multiLine: boolean; type: string };

// A box that asks for words, even when it also names a fact ("Describe your notice period").
const OPEN_QUESTION =
  /^(?:why|describe|explain|tell|share|what (?:interests|excites|motivates|makes|draws)|how (?:would|did|do) you|introduce|write)\b|\bcover letter\b|\bmessage\b|\bnote to\b/i;

// A single-line box asking for one of these wants a fact the user knows, not words.
const FACT_QUESTION =
  /\b(?:how many|years?|months?|ctc|salary|compensation|stipend|pay|notice|date|dob|birth|age|phone|mobile|contact number|e-?mail|zip|pin ?code|postal|city|state|country|address|gpa|cgpa|percentage|marks|score|grade|name|id|number)\b/i;

// A single-line yes/no question ("Do you have a valid passport?") wants one word from the user.
const YES_NO_QUESTION = /^(?:are|do|does|did|have|has|is|will|can|could)\s+you\b/i;

// Input types that hold a fact, never a written answer.
// Not 'url': a link question ("Link to your work") is answered from the profile's links,
// and the server drops any link the profile does not have.
const FACT_INPUT_TYPES = new Set(['email', 'tel', 'number']);

// Facts only the user knows: a model would only guess them.
const FACT_KINDS = new Set<Kind>([
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
]);

// Profile fields a model can still write well: a role description, a headline, a skills summary.
const WRITTEN_KINDS = new Set<Kind>(['question', 'why_this_role', 'job_description', 'headline', 'skills']);

/**
 * Whether a box asks for words a model can write: any multi-line box, or a
 * single-line one whose question is not a fact only the user knows (a number,
 * a date, a link, a name). Pure, so it can be tested without a page.
 */
export function asksForWords(box: Box, question: string, kind: Kind | null): boolean {
  if (!box.multiLine && FACT_INPUT_TYPES.has(box.type)) return false;
  if (kind !== null && (FACT_KINDS.has(kind) || !WRITTEN_KINDS.has(kind))) return false;
  if (box.multiLine) return true;
  if (OPEN_QUESTION.test(question)) return true;
  return !FACT_QUESTION.test(question) && !YES_NO_QUESTION.test(question);
}
