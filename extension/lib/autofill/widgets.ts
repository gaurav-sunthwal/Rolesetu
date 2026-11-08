/**
 * Custom dropdown widget detection and interaction.
 *
 * Many enterprise ATS platforms (SAP SuccessFactors / Capgemini, Taleo,
 * Greenhouse, Lever, Workday, iCIMS...) do NOT use native <select> elements.
 * Instead they render a custom combobox pattern:
 *
 *   <label for="tor__fcustLegalToWork">Are you legally entitled…?</label>
 *   <input type="text"   role="combobox" aria-label="…" id="13:_input">   ← visible
 *   <input type="hidden" id="tor__fcustLegalToWork" value="">              ← real value
 *
 * The label points at the hidden input.  The combobox shows human-readable
 * text ("Yes", "No") while the hidden field stores an opaque ID ("43568").
 *
 * Problems this causes:
 *  - `findFields` sees `input[type=text]` with `role=combobox` but no <select>
 *    → no dropdown matching, no learning.
 *  - The `change` event on the hidden field is fired by the site's own JS
 *    → `event.isTrusted = false` → our learn.ts ignores it.
 *
 * Solution:
 *  - Detect these pairs by looking for hidden inputs whose <label> exists, and
 *    a nearby combobox input that shares the same aria-label / aria-labelledby.
 *  - Represent them as `WidgetField` objects alongside normal `Field` objects.
 *  - Watch the hidden input's `value` attribute with MutationObserver (the
 *    site's JS sets it via setAttribute or direct property) so we learn the
 *    human-readable text the combobox is showing, not the opaque internal ID.
 *
 * Supported widget patterns (all detected automatically):
 *  1. SAP SuccessFactors / Capgemini  – label[for=hidden], nearby combobox
 *  2. Greenhouse / Lever              – select replaced by a div[role=listbox]
 *  3. Workday                         – input[data-uxi-widget-type=selectWidget]
 *  4. Taleo                           – select hidden with display:none, custom div
 *
 * For FILLING: we write the human-readable value into the combobox and then
 * try clicking/firing events on it so the widget framework picks it up.
 *
 * For LEARNING: we watch the combobox's displayed text (its `value` attribute)
 * using MutationObserver.  When it changes to something non-placeholder we save
 * it as the answer for this field's question key.
 */

import { type Kind } from './fields';

/** A custom-widget "field" — backed by a hidden input but readable via a combobox. */
export type WidgetField = {
  /** The hidden <input> that stores the selected value (opaque ID). */
  hidden: HTMLInputElement;
  /** The visible <input type="text" role="combobox"> or equivalent. */
  combobox: HTMLInputElement;
  /** The question key used for storage, same format as Field.key. */
  key: string;
  /** The human-readable question label. */
  label: string;
  /** Kind classification (same as Field.kind). */
  kind: Kind;
  /** Short display name for "learned" toasts. */
  question: string | null;
};

// ─── Helpers ────────────────────────────────────────────────────────────────

const PLACEHOLDER_RE = /^(?:no selection|select\.\.\.|please select|choose|--|none|select one)$/i;

function norm(s: string): string {
  return s.trim().toLowerCase();
}

/** Whether a combobox is still on its placeholder (nothing selected). */
export function comboboxIsEmpty(cb: HTMLInputElement): boolean {
  const v = norm(cb.value);
  return v === '' || PLACEHOLDER_RE.test(v);
}

// ─── Detection ──────────────────────────────────────────────────────────────

/**
 * Finds all custom-widget dropdown fields on the page.
 *
 * Strategy:
 *  - Look for every `input[type="hidden"]` that has a `<label for="…">`.
 *  - Then find the matching combobox: an `input[role="combobox"]` whose
 *    `aria-label` matches the label text, OR that is the nearest sibling
 *    combobox inside the same container.
 *  - Skip pairs that are inside aria-hidden trees or our own UI root.
 */
export function findWidgetFields(doc: Document): WidgetField[] {
  const results: WidgetField[] = [];

  for (const hidden of doc.querySelectorAll<HTMLInputElement>('input[type="hidden"]')) {
    if (hidden.closest('rolesetu-root, [aria-hidden="true"]')) continue;
    if (!hidden.id) continue;

    // Must have a <label> pointing at it.
    const labelEl = doc.querySelector<HTMLLabelElement>(`label[for="${CSS.escape(hidden.id)}"]`);
    if (!labelEl) continue;

    const labelText = getLabelText(labelEl);
    if (!labelText || labelText.length < 3) continue;

    // Find the matching combobox.
    const combobox = findCombobox(doc, hidden, labelText);
    if (!combobox) continue;
    // Skip disabled comboboxes.
    if (combobox.disabled) continue;

    const kind = kindFromLabel(labelText);
    const key = keyFromLabel(kind, labelText, hidden);

    results.push({
      hidden,
      combobox,
      key,
      label: labelText,
      kind,
      question: labelText.length <= 120 ? labelText : labelText.slice(0, 120),
    });
  }

  return results;
}

/** Extract the human-readable text of a label, stripping required-star spans. */
function getLabelText(label: HTMLLabelElement): string {
  const clone = label.cloneNode(true) as HTMLLabelElement;
  // Remove required markers and hidden accessibility spans.
  clone.querySelectorAll('.required, .sr-only, [aria-hidden]').forEach((el) => el.remove());
  return clone.textContent?.replace(/\s+/g, ' ').trim() ?? '';
}

/**
 * Find the combobox for a given hidden input + label text.
 * Tries three strategies in order:
 *  1. A combobox whose aria-label matches.
 *  2. A combobox inside the same parent container as the hidden input.
 *  3. The combobox with id = hidden.id.replace("tor__f", "") + ":_input"
 *     (SAP SuccessFactors naming convention).
 */
function findCombobox(
  doc: Document,
  hidden: HTMLInputElement,
  labelText: string,
): HTMLInputElement | null {
  const nLabel = norm(labelText);

  // Strategy 1: aria-label exact or close match.
  for (const cb of doc.querySelectorAll<HTMLInputElement>('input[role="combobox"]')) {
    if (cb.disabled) continue;
    const ariaLabel = norm(cb.getAttribute('aria-label') ?? '');
    if (ariaLabel && (ariaLabel === nLabel || nLabel.startsWith(ariaLabel.slice(0, 30)))) {
      return cb;
    }
  }

  // Strategy 2: nearest combobox sibling inside the same container.
  const container = hidden.closest('td, div.displayInlineBlock, div.rcmFormElement, .fd-input-group');
  if (container) {
    const cb = container.querySelector<HTMLInputElement>('input[role="combobox"]');
    if (cb && !cb.disabled) return cb;
  }

  // Strategy 3: SAP id convention  "tor__fFieldName" → "N:_input".
  // The combobox id is built by the widget renderer and doesn't follow a simple
  // rule, so we skip this and rely on strategy 1/2.

  return null;
}

// ─── Kind / Key classification ───────────────────────────────────────────────

// Same rules as fields.ts RULES, applied to label text.
const KIND_RULES: [Kind, RegExp][] = [
  ['work_authorization', /work authori[sz]ation|authori[sz]ed to work|legally (?:authori[sz]ed|eligible)|right to work|legally entitled to work/],
  ['gender', /\bgender\b|how do you identify|identify/],
  ['nationality', /nationality|citizenship/],
  ['relocation', /relocat/],
  ['notice_period', /notice period/],
  ['heard_from', /how did you (?:hear|find)|source of (?:application|hire)/],
  ['date_of_birth', /date of birth|birth ?date|\bdob\b/],
  ['postal_code', /postal|zip|pin ?code/],
  ['location', /country of residence|country|location|\bcity\b/],
  ['phone', /phone|mobile|contact (?:no|number)/],
];

function kindFromLabel(labelText: string): Kind {
  const n = norm(labelText);
  for (const [kind, pattern] of KIND_RULES) {
    if (pattern.test(n)) return kind;
  }
  return 'question';
}

/** Stable storage key for a widget field. */
function keyFromLabel(kind: Kind, labelText: string, hidden: HTMLInputElement): string {
  if (kind !== 'question') return kind;
  // Use the label text (truncated) for custom questions.
  const words = norm(labelText)
    .slice(0, 100)
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  if (words.length > 2) return `q_${words.slice(0, 56).replace(/_+$/g, '')}`;
  // Last resort: use the hidden input's name or id.
  const fallback = (hidden.getAttribute('name') || hidden.id).replace(/[^a-z0-9]+/gi, '_').toLowerCase();
  return `q_${fallback.slice(0, 56)}`;
}

// ─── Learning (MutationObserver) ─────────────────────────────────────────────

/**
 * Watches all custom-widget comboboxes on the page.
 * When the user picks a value (the combobox text changes to something
 * non-placeholder), calls `onPicked(key, visibleText)`.
 *
 * Returns a cleanup function.
 */
export function watchWidgets(
  doc: Document,
  onPicked: (key: string, visibleText: string, kind: Kind, label: string) => void,
): () => void {
  const cleanups: (() => void)[] = [];

  const attach = () => {
    const widgets = findWidgetFields(doc);
    for (const widget of widgets) {
      if ((widget.combobox as HTMLInputElement & { _rsWatched?: boolean })._rsWatched) continue;
      (widget.combobox as HTMLInputElement & { _rsWatched?: boolean })._rsWatched = true;

      // Watch for the combobox text value changing (the site sets it directly).
      const observer = new MutationObserver(() => {
        const text = widget.combobox.value.trim();
        if (text && !PLACEHOLDER_RE.test(text)) {
          onPicked(widget.key, text, widget.kind, widget.label);
        }
      });
      observer.observe(widget.combobox, { attributes: true, attributeFilter: ['value'] });

      // Also listen for a regular input event (some frameworks fire it).
      const onInput = () => {
        const text = widget.combobox.value.trim();
        if (text && !PLACEHOLDER_RE.test(text)) {
          onPicked(widget.key, text, widget.kind, widget.label);
        }
      };
      widget.combobox.addEventListener('change', onInput);
      widget.combobox.addEventListener('input', onInput);

      cleanups.push(() => {
        observer.disconnect();
        widget.combobox.removeEventListener('change', onInput);
        widget.combobox.removeEventListener('input', onInput);
      });
    }
  };

  // Attach immediately and re-attach after DOM changes (lazy-loaded widgets).
  attach();
  const domObserver = new MutationObserver(attach);
  domObserver.observe(doc.body, { childList: true, subtree: true });

  return () => {
    domObserver.disconnect();
    cleanups.forEach((fn) => fn());
  };
}

// ─── Filling ─────────────────────────────────────────────────────────────────

/**
 * Tries to set a custom widget to the given visible text value.
 *
 * Approach:
 *  1. Set the combobox's value to the text via the native setter (React compat).
 *  2. Fire `input` and `change` events so the widget framework reacts.
 *  3. If the widget has a dropdown list open (ul[role=listbox]), click the
 *     matching option.
 *
 * Returns true if the combobox ended up showing a non-placeholder value.
 */
export function fillWidget(widget: WidgetField, values: string[]): boolean {
  const { combobox } = widget;

  // Try each candidate value.
  for (const value of values) {
    if (!value) continue;

    // Write via native setter (bypasses React's read-only guard).
    const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    nativeSetter?.call(combobox, value);
    combobox.dispatchEvent(new Event('input', { bubbles: true }));
    combobox.dispatchEvent(new Event('change', { bubbles: true }));

    // Also fire a keydown to open the dropdown if it's event-driven.
    combobox.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'ArrowDown' }));
    combobox.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'ArrowDown' }));

    // If a listbox appeared in the DOM, click the best match.
    const clicked = tryClickOption(combobox.ownerDocument, value);
    if (clicked) return true;

    // Check if the combobox now shows our value (widget accepted it).
    if (!comboboxIsEmpty(combobox)) return true;
  }

  return !comboboxIsEmpty(combobox);
}

/** After triggering the combobox, look for a visible listbox and click the best option. */
function tryClickOption(doc: Document, value: string): boolean {
  const nv = norm(value);
  // Wait a tiny tick for the dropdown to open.
  const listboxes = doc.querySelectorAll<HTMLElement>(
    '[role="listbox"], [role="option"], .rcmpaginatedselectitem:not(input):not(button)',
  );
  for (const item of listboxes) {
    const text = norm(item.textContent ?? '');
    if (text === nv || text.startsWith(nv) || nv.startsWith(text)) {
      item.click();
      return true;
    }
  }
  return false;
}
