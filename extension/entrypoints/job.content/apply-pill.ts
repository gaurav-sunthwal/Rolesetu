/**
 * Puts the match score next to the page's own Apply button, so it is seen at
 * the moment of deciding. These pills live in the host page (not our shadow
 * root), so every style is set inline and nothing depends on the site's CSS.
 */

import { APPLY, CONTROLS, labelOf } from '@/lib/apply-controls';

const MARK = 'data-rolesetu-pill';
const MAX_PILLS = 3;
const CANDIDATES = CONTROLS;

export type PillState = { text: string; color: string } | null;

function isVisible(element: Element): boolean {
  if (!(element instanceof HTMLElement)) return false;
  const box = element.getBoundingClientRect();
  return box.width > 0 && box.height > 0 && getComputedStyle(element).visibility !== 'hidden';
}

function findApplyButtons(): HTMLElement[] {
  const found: HTMLElement[] = [];
  for (const element of document.querySelectorAll(CANDIDATES)) {
    if (found.length >= MAX_PILLS) break;
    if (element.hasAttribute(MARK) || element.closest('rolesetu-root')) continue;
    const label = labelOf(element);
    if (label.length > 40 || !APPLY.test(label) || !isVisible(element)) continue;
    // A button nested in another match ("<a><button>Apply</button></a>") counts once.
    if (found.some((other) => other.contains(element) || element.contains(other))) continue;
    found.push(element as HTMLElement);
  }
  return found;
}

function buildPill(state: NonNullable<PillState>, onClick: () => void): HTMLButtonElement {
  const pill = document.createElement('button');
  pill.type = 'button';
  pill.setAttribute(MARK, '');
  pill.setAttribute('aria-label', `Rolesetu: ${state.text}. Show details.`);
  pill.style.cssText = [
    'all: initial',
    'display: inline-flex',
    'align-items: center',
    'gap: 7px',
    'margin: 6px 10px',
    'padding: 7px 13px',
    'border-radius: 999px',
    `border: 1.5px solid ${state.color}`,
    'background: #ffffff',
    'color: #14151a',
    'font: 600 13px/1 Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
    'white-space: nowrap',
    'cursor: pointer',
    'vertical-align: middle',
    'box-shadow: 0 2px 10px rgba(15, 20, 40, .12)',
  ].join(';');

  const dot = document.createElement('span');
  dot.style.cssText = `width:8px;height:8px;border-radius:50%;background:${state.color};flex:none`;
  const text = document.createElement('span');
  text.textContent = state.text;
  pill.append(dot, text);

  pill.addEventListener('click', (event) => {
    // Never let this trigger the site's own Apply action or a surrounding link.
    event.preventDefault();
    event.stopPropagation();
    onClick();
  });
  return pill;
}

export function removeApplyPills(): void {
  document.querySelectorAll(`[${MARK}]`).forEach((pill) => pill.remove());
}

/**
 * Makes the page show `state` beside each Apply button. Returns how many
 * buttons carry a pill, so the caller knows whether a fallback is needed.
 */
export function showApplyPills(state: PillState, onClick: () => void): number {
  removeApplyPills();
  if (state === null) return 0;
  const buttons = findApplyButtons();
  for (const button of buttons) {
    button.insertAdjacentElement('afterend', buildPill(state, onClick));
  }
  return buttons.length;
}
