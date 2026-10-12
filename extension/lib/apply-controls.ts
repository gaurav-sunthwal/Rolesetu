/** How a page's own "Apply" buttons are recognised. Shared by every part that looks for them. */

export const CONTROLS = 'button, a, input[type="submit"], input[type="button"], [role="button"]';

// "Apply", "Apply now", "Easy Apply", "Apply for this job", "Apply on company site"...
export const APPLY =
  /^(?:easy |quick |1[- ]click )?apply(?: now| here| for (?:this|the) (?:job|role|position|internship)| to (?:this )?job| on company (?:web)?site| on employer site)?$/i;

const MAX_LABEL = 40;

export function labelOf(element: Element): string {
  const raw = element instanceof HTMLInputElement ? element.value : (element.textContent ?? '');
  return raw.replace(/\s+/g, ' ').trim();
}

export function isApplyControl(element: Element): boolean {
  // Length first: it skips the regex for the many long links on a page.
  if ((element.textContent ?? '').length > MAX_LABEL * 3) return false;
  const label = labelOf(element);
  return label.length <= MAX_LABEL && APPLY.test(label);
}

export function hasApplyControl(doc: Document): boolean {
  for (const element of doc.querySelectorAll(CONTROLS)) {
    if (isApplyControl(element)) return true;
  }
  return false;
}
