/**
 * A small bar under the field being answered, with what fits the field right now:
 *
 * - "Use it": on an empty field, an answer from the page scan: the user's answer
 *   to the same question worded differently, or one made for this company. No
 *   request on focus.
 * - "Write with AI" / "Improve with AI": on a written question, the model writes an
 *   answer from the profile and the job, or improves what is in the box, and fills
 *   it in as a draft. Only when the user clicks; free up to a daily allowance.
 * - "Save answer": on any question whose answer belongs in saved answers, once the
 *   user has typed one. Answers are also learned when the user leaves the field,
 *   so a forgotten click loses nothing. Profile fields (name, links...) get no
 *   button: they are changed on the profile.
 *
 * The bar lives in a shadow root, so the host page's styles cannot reach it and
 * its own cannot leak into the page.
 */

import { type Field, findFields, hasApplicationForm, isSearchLike, keyForQuestion } from './fields';
import { type JobNames, markDraft, setText, type Suggestion, templateParts } from './fill';
import { answerName, isLearnedKind, isPrivateQuestion, type Learned } from './learn';
import { track, trackOnce } from '../analytics';
import { saveSiteProfile } from './site-profiles';

/** Characters typed before "Save answer" is offered. */
const MIN_LENGTH = 2;
/** How long "Saved" and "Filled in" stay before the helper goes away. */
const CONFIRM_MS = 2000;
/** Grace period on blur, so moving the pointer to the helper does not hide it. */
const HIDE_AFTER_MS = 300;

const HOST_ATTRIBUTE = 'data-rolesetu-helpers';

const GENERIC_OR_INVALID_PROMPT =
  /^(?:enter(?:\s+(?:your\s+)?text|\s*\.{3})?|type(?:\s+(?:here|your\s+answer|text)|\s*\.{3})?|write(?:\s+here|\s+your\s+answer)?|your\s+answer|answer(?:\s+here)?|this\s+field\s+is\s+required|required|optional|select|choose|n\/a|none|placeholder|input|text|value|chars?\s+left.*|\d+\/\d+|\bmax\s+\d+.*)$/i;

type TextField = HTMLInputElement | HTMLTextAreaElement;

function clean(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function isValidPrompt(text: string | null | undefined): text is string {
  if (!text) return false;
  // "ⓘ This field is required" is the same as "This field is required".
  const cleaned = clean(text).replace(/^[^\p{L}\d]+/u, '');
  if (cleaned.length < 4 || cleaned.length > 1000) return false;
  if (GENERIC_OR_INVALID_PROMPT.test(cleaned)) return false;
  return /[a-zA-Z]{2,}/.test(cleaned);
}

export type FieldInfo = {
  key: string;
  question: string;
  /** The field as `findFields` reads it, or null when it is not one autofill sees. */
  field: Field | null;
};

/** The words a person reads near a field that `findFields` could not label. */
function nearbyPrompt(el: TextField): string | null {
  const doc = el.ownerDocument;
  const candidates: string[] = [];
  if (el.id) {
    try {
      candidates.push(doc.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent ?? '');
    } catch {
      // An id CSS cannot select: the other sources still apply.
    }
  }
  const wrapping = el.closest('label');
  if (wrapping) {
    const copy = wrapping.cloneNode(true) as HTMLElement;
    copy.querySelectorAll('input, textarea, select').forEach((control) => control.remove());
    candidates.push(copy.textContent ?? '');
  }
  candidates.push(el.getAttribute('aria-label') ?? '');
  const labelledBy = el.getAttribute('aria-labelledby');
  if (labelledBy) {
    candidates.push(labelledBy.split(/\s+/).map((id) => doc.getElementById(id)?.textContent ?? '').join(' '));
  }
  for (const start of [el, el.parentElement]) {
    for (let prev = start?.previousElementSibling; prev; prev = prev.previousElementSibling) {
      if (!prev.querySelector('input, textarea, select')) candidates.push(prev.textContent ?? '');
    }
  }
  const container = el.closest(
    '.assessment_question, .form-group, .form-field, .form-row, .field, fieldset, [class*="question"], [class*="field"], li, td',
  );
  if (container) {
    for (const prompt of container.querySelectorAll('label, legend, h1, h2, h3, h4, h5, h6, p, strong, span, div')) {
      if (!prompt.contains(el) && !prompt.querySelector('input, textarea, select')) {
        candidates.push(prompt.textContent ?? '');
      }
    }
  }
  candidates.push(el.getAttribute('placeholder') ?? '');
  return candidates.map(clean).find(isValidPrompt) ?? null;
}

/**
 * The key and question for a text field, or null when no question can be read
 * beside it (an answer saved under a made-up key would never be found again).
 */
export function extractFieldInfo(el: TextField): FieldInfo | null {
  const field = findFields(el.ownerDocument).find((candidate) => candidate.element === el) ?? null;
  if (field) {
    const question = field.kind === 'question' ? field.question : answerName(field);
    return isValidPrompt(question) ? { key: field.key, question: clean(question), field } : null;
  }
  const prompt = nearbyPrompt(el);
  return prompt ? { key: keyForQuestion(prompt), question: prompt.slice(0, 300), field: null } : null;
}

function looksPrivate(el: TextField, info: FieldInfo): boolean {
  const words = [info.question, el.getAttribute('name') ?? '', el.id, el.getAttribute('placeholder') ?? ''];
  return isPrivateQuestion(words.join(' '));
}

// ─── Look ─────────────────────────────────────────────────────────────────────

const STYLES = `
:host { all: initial; }
.bar {
  position: fixed;
  z-index: 2147483647;
  display: none;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  max-width: min(520px, calc(100vw - 16px));
  font: 600 12px/1.3 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
.bar[data-shown] { display: flex; }
.helper {
  display: none;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  padding: 6px 12px;
  font: inherit;
  border-radius: 999px;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.16);
  transition: background-color 0.15s ease, transform 0.1s ease;
}
.helper[data-shown] { display: inline-flex; }
.helper:active { transform: scale(0.97); }
.helper:focus-visible { outline: 2px solid #1d4ed8; outline-offset: 2px; }
.helper[data-state="busy"] { cursor: progress; opacity: 0.85; }
.save { color: #fff; background: #2563eb; border: 1px solid #1d4ed8; }
.save:hover { background: #1d4ed8; }
.save[data-state="saved"] { background: #15803d; border-color: #166534; cursor: default; }
.save[data-state="error"] { background: #b91c1c; border-color: #991b1b; }
.ai { color: #5b21b6; background: #f5f3ff; border: 1px solid #c4b5fd; }
.ai:hover { background: #ede9fe; }
.suggest { color: #1e293b; background: #fff; border: 1px solid #cbd5e1; font-weight: 500; }
.suggest:hover { background: #f8fafc; border-color: #94a3b8; }
.suggest .from { overflow: hidden; text-overflow: ellipsis; color: #475569; }
.suggest .use { flex-shrink: 0; padding: 2px 9px; border-radius: 999px; color: #fff; background: #2563eb; font-weight: 600; }
.note {
  display: none;
  flex-basis: 100%;
  padding: 6px 10px;
  border-radius: 8px;
  color: #1e293b;
  background: #fff;
  border: 1px solid #cbd5e1;
  font-weight: 500;
  white-space: normal;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
}
.note[data-shown] { display: block; }
.note[data-tone="error"] { color: #991b1b; background: #fef2f2; border-color: #fecaca; }
.note[data-tone="done"] { color: #166534; background: #f0fdf4; border-color: #bbf7d0; }
@media (prefers-reduced-motion: reduce) { .helper { transition: none; } .helper:active { transform: none; } }
`;

function button(className: string): HTMLButtonElement {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = `helper ${className}`;
  return element;
}

function makeBar() {
  document.querySelector(`[${HOST_ATTRIBUTE}]`)?.remove();
  const host = document.createElement('div');
  host.setAttribute(HOST_ATTRIBUTE, '');
  const root = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = STYLES;
  const bar = document.createElement('div');
  bar.className = 'bar';
  const suggest = button('suggest');
  const ai = button('ai');
  const save = button('save');
  const note = document.createElement('div');
  note.className = 'note';
  note.setAttribute('role', 'status');
  note.setAttribute('aria-live', 'polite');
  bar.append(suggest, ai, save, note);
  root.append(style, bar);
  document.documentElement.append(host);
  return { host, bar, suggest, ai, save, note };
}

function placeBelow(bar: HTMLElement, el: HTMLElement): void {
  const box = el.getBoundingClientRect();
  const height = bar.offsetHeight || 32;
  let top = box.bottom + 6;
  if (top + height > window.innerHeight - 6) top = box.top - height - 6;
  const wantTop = Math.max(6, Math.min(top, window.innerHeight - height - 6));
  const wantLeft = Math.max(6, Math.min(box.left, window.innerWidth - (bar.offsetWidth || 200) - 6));
  bar.style.top = `${wantTop}px`;
  bar.style.left = `${wantLeft}px`;
  // Inside a pop-up that is moved or scaled, "fixed" is measured from the pop-up,
  // not the window: measure where the bar landed and correct by the difference.
  const landed = bar.getBoundingClientRect();
  if (landed.width > 0 && (Math.abs(landed.top - wantTop) > 1 || Math.abs(landed.left - wantLeft) > 1)) {
    bar.style.top = `${2 * wantTop - landed.top}px`;
    bar.style.left = `${2 * wantLeft - landed.left}px`;
  }
}

/**
 * Keeps the bar where the field is drawn. A pop-up opened as a modal <dialog>
 * is drawn above everything else on the page, so a bar outside it would be
 * hidden behind it: the bar moves inside the pop-up while a field in it is used.
 */
function layerFor(el: Element): Element {
  try {
    return el.closest('dialog[open], [popover]:popover-open') ?? document.documentElement;
  } catch {
    // A browser that does not know :popover-open.
    return el.closest('dialog[open]') ?? document.documentElement;
  }
}

const show = (element: HTMLElement, shown: boolean) => {
  if (shown) element.dataset.shown = '';
  else delete element.dataset.shown;
};

// ─── Behaviour ────────────────────────────────────────────────────────────────

type SaveState = 'idle' | 'busy' | 'saved' | 'error';

const SAVE_LABELS: Record<SaveState, string> = {
  idle: 'Save answer',
  busy: 'Saving…',
  saved: 'Saved for next time ✓',
  error: 'Could not save. Try again',
};

// A single-line box still deserves AI when it asks for words, not a fact.
const OPEN_QUESTION =
  /^(?:why|describe|explain|tell|share|what (?:interests|excites|motivates|makes|draws)|how (?:would|did|do) you|introduce|write)\b|\bcover letter\b|\bmessage\b|\bnote to\b/i;

// Facts only the user knows: a model would only guess them.
const FACT_KINDS = new Set<Field['kind']>([
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

/** Saves answers; resolves to whether the server kept them. */
export type SaveFn = (learned: Learned[]) => Promise<boolean>;
/** An answer for a field's key from the page scan, if there is one. */
export type SuggestFn = (key: string) => Suggestion | undefined;
/** What the AI buttons ask for, and what comes back. */
export type AiRequest = { mode: 'write' | 'improve'; question: string; context: string; current: string; maxLength: number };
export type AiResult = { ok: true; text: string; left: number | null; removed: string[] } | { ok: false; message: string };
export type AiFn = (request: AiRequest) => Promise<AiResult>;

/**
 * Attaches the bar to the page. `known` is what is saved already (null until
 * loaded), so an answer that is already saved is not offered for saving again.
 * `contextOf` gives the words around a box (a pop-up's heading). Returns the cleanup.
 */
export function attachSaveButtons(
  known: () => Record<string, string> | null,
  saveFn: SaveFn,
  suggest: SuggestFn,
  writeWithAi: AiFn,
  contextOf: (element: Element) => string,
  jobNames: () => JobNames,
): () => void {
  const { host, bar, suggest: pill, ai, save, note } = makeBar();

  // `ai`: whether the box has a reason for AI, worked out once per focus.
  let active: { el: TextField; info: FieldInfo; ai: boolean } | null = null;
  let saveState: SaveState = 'idle';
  let aiBusy = false;
  let offered: Suggestion | null = null;
  let hideTimer: ReturnType<typeof setTimeout> | undefined;
  let noteTimer: ReturnType<typeof setTimeout> | undefined;

  const setSaveState = (state: SaveState) => {
    saveState = state;
    save.dataset.state = state;
    save.textContent = SAVE_LABELS[state];
  };

  const say = (text: string, tone: 'error' | 'done' | 'info', forMs?: number) => {
    clearTimeout(noteTimer);
    note.textContent = text;
    note.dataset.tone = tone;
    show(note, true);
    reposition();
    if (forMs) noteTimer = setTimeout(() => show(note, false), forMs);
  };

  const hideAll = () => {
    clearTimeout(noteTimer);
    for (const element of [bar, pill, ai, save, note]) show(element, false);
    setSaveState('idle');
    offered = null;
  };

  const reposition = () => {
    if (!active) return;
    if (!active.el.isConnected) {
      active = null;
      hideAll();
      return;
    }
    const anything = [pill, ai, save, note].some((element) => element.dataset.shown !== undefined);
    show(bar, anything);
    if (anything) placeBelow(bar, active.el);
  };

  /**
   * Whether this box has a reason for AI, so no click (and no paid call) is ever
   * invited for nothing: a written answer (a multi-line box, or an open question
   * like "Why..." or "Describe..."), in an application (an Apply pop-up, a form,
   * or a page that is one), and not a fact only the user knows.
   */
  const aiCanWrite = (el: TextField, info: FieldInfo) => {
    if (info.field !== null && FACT_KINDS.has(info.field.kind)) return false;
    const written = el instanceof HTMLTextAreaElement || OPEN_QUESTION.test(info.question);
    if (!written) return false;
    return (
      el.closest('form, dialog, [role="dialog"], [aria-modal="true"], fieldset') !== null ||
      hasApplicationForm(el.ownerDocument)
    );
  };

  /** Shows what fits the field as it is now. */
  const update = () => {
    if (!active || saveState === 'busy' || aiBusy) return;
    const { el, info } = active;
    const value = el.value.trim();
    const profileField = info.field !== null && !isLearnedKind(info.field.kind);

    if (value === '') {
      show(save, false);
      const answer = suggest(info.key);
      offered = answer ?? null;
      if (answer) {
        pill.replaceChildren();
        const from = document.createElement('span');
        from.className = 'from';
        from.textContent = answer.label;
        const use = document.createElement('span');
        use.className = 'use';
        use.textContent = 'Use it';
        pill.append(from, use);
        pill.setAttribute('aria-label', `${answer.label}. Use it: ${answer.answer.slice(0, 200)}`);
        pill.title = answer.answer.slice(0, 300);
        trackOnce(info.key, 'suggestion_shown', { props: { source: answer.source } });
      }
      show(pill, Boolean(answer));
      ai.textContent = '✨ Write with AI';
      show(ai, !profileField && active.ai);
      reposition();
      return;
    }

    show(pill, false);
    ai.textContent = '✨ Improve with AI';
    show(ai, !profileField && active.ai && value.length >= 10);
    const savedAlready = known()?.[info.key] === value;
    if (profileField || value.length < MIN_LENGTH || savedAlready) {
      if (saveState !== 'saved') show(save, false);
    } else if (save.dataset.shown === undefined || saveState === 'error' || saveState === 'saved') {
      setSaveState('idle');
      show(save, true);
    }
    reposition();
  };

  const onFocusIn = (event: FocusEvent) => {
    const target = event.composedPath()[0];
    if (target instanceof Node && host.contains(target)) return;
    clearTimeout(hideTimer);
    if (
      !(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) ||
      (target instanceof HTMLInputElement && !['', 'text', 'number', 'url', 'tel', 'email'].includes(target.type)) ||
      target.closest('rolesetu-root') ||
      isSearchLike(target)
    ) {
      active = null;
      hideAll();
      return;
    }
    if (active?.el !== target) {
      hideAll();
      // Read once per focus: reading the whole form on every keystroke would slow the page.
      const info = extractFieldInfo(target);
      active = info && !looksPrivate(target, info) ? { el: target, info, ai: aiCanWrite(target, info) } : null;
      const layer = layerFor(target);
      if (active && host.parentElement !== layer) layer.append(host);
    }
    update();
  };

  const onInput = (event: Event) => {
    if (event.isTrusted && active && event.target === active.el) update();
  };

  const onFocusOut = () => {
    if (saveState === 'busy' || aiBusy) return;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (document.activeElement !== active?.el) {
        active = null;
        hideAll();
      }
    }, HIDE_AFTER_MS);
  };

  const onSave = async () => {
    if (!active || saveState === 'busy' || saveState === 'saved') return;
    const { el, info } = active;
    const value = el.value.trim();
    if (value.length < MIN_LENGTH) return;
    setSaveState('busy');
    const ok = await saveFn([{ answer: { question_key: info.key, answer: value }, name: info.question }]).catch(
      () => false,
    );
    if (!ok) {
      setSaveState('error');
      return;
    }
    void saveSiteProfile(document.location.hostname, { [info.key]: value });
    setSaveState('saved');
    // Say whether it became reusable: "Loopr AI" kept as is would be sent to the next company.
    const names = jobNames();
    const { swapped } = templateParts(value, names);
    track('answer_saved', { props: { via: 'button', reusable: swapped.length > 0 } });
    const quoted = swapped.map((name) => `“${name}”`).join(' and ');
    if (swapped.length > 0) {
      say(
        `Saved as a reusable answer: ${quoted} will be replaced with each company's own name and role.`,
        'done',
        6000,
      );
    } else if (value.length >= 40 && names.company === null) {
      say(
        "Saved. This page did not say the company's name, so it is kept as written: check the name when it is reused.",
        'info',
        6000,
      );
    } else {
      say('Saved. The next form that asks this, however it is worded, gets it.', 'done', CONFIRM_MS + 1500);
    }
  };

  const onUse = () => {
    if (!active || !offered) return;
    const { el } = active;
    track('suggestion_used', { props: { source: offered.source } });
    setText(el, offered.answer.slice(0, el.maxLength > 0 ? el.maxLength : undefined));
    if (offered.draft) markDraft(el);
    el.focus();
    show(pill, false);
    say('Filled in. Read it and make it yours before you submit.', 'done', CONFIRM_MS);
    update();
  };

  const onAi = async () => {
    if (!active || aiBusy) return;
    const { el, info } = active;
    const current = el.value.trim();
    aiBusy = true;
    ai.dataset.state = 'busy';
    const label = ai.textContent;
    ai.textContent = current ? 'Improving…' : 'Writing…';
    say(current ? 'Improving your answer with AI…' : 'Writing an answer from your profile and this job…', 'info');
    const result = await writeWithAi({
      mode: current ? 'improve' : 'write',
      question: info.question,
      context: contextOf(el),
      current,
      maxLength: el.maxLength > 0 ? el.maxLength : 2000,
    }).catch((): AiResult => ({ ok: false, message: 'AI could not answer just now. Try again in a moment.' }));
    aiBusy = false;
    delete ai.dataset.state;
    ai.textContent = label;
    if (!active || active.el !== el) return;
    if (!result.ok) {
      say(result.message, 'error');
      return;
    }
    setText(el, result.text);
    markDraft(el);
    el.focus();
    const left =
      result.left === null ? '' : ` ${result.left} AI ${result.left === 1 ? 'credit' : 'credits'} left this month.`;
    const checked = result.removed.length > 0 ? ' Claims your profile does not back were left out.' : '';
    say(`Written. Read it and make it yours before you submit.${checked}${left}`, 'done', 6000);
    update();
  };

  // Keep focus in the field while the bar is pressed, so the page does not see a blur.
  const keepFocus = (event: Event) => event.preventDefault();
  for (const helper of [pill, ai, save]) {
    helper.addEventListener('mousedown', keepFocus);
    helper.addEventListener('pointerdown', keepFocus);
  }
  save.addEventListener('click', () => void onSave());
  pill.addEventListener('click', onUse);
  ai.addEventListener('click', () => void onAi());

  document.addEventListener('focusin', onFocusIn, true);
  document.addEventListener('focusout', onFocusOut, true);
  document.addEventListener('input', onInput, true);
  window.addEventListener('scroll', reposition, { passive: true, capture: true });
  window.addEventListener('resize', reposition, { passive: true });

  return () => {
    clearTimeout(hideTimer);
    clearTimeout(noteTimer);
    document.removeEventListener('focusin', onFocusIn, true);
    document.removeEventListener('focusout', onFocusOut, true);
    document.removeEventListener('input', onInput, true);
    window.removeEventListener('scroll', reposition, true);
    window.removeEventListener('resize', reposition);
    host.remove();
  };
}
