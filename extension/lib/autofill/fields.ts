/**
 * Reads a form the way a person does: by the words beside each box. Every
 * field gets a `kind` ("email", "company"...) from its label, placeholder and
 * name. Nothing here writes to the page.
 */

export type Kind =
  | 'first_name'
  | 'last_name'
  | 'full_name'
  | 'email'
  | 'phone'
  | 'location'
  | 'linkedin'
  | 'github'
  | 'portfolio'
  | 'headline'
  | 'years'
  | 'skills'
  | 'company'
  | 'title'
  | 'job_start'
  | 'job_end'
  | 'job_description'
  | 'school'
  | 'degree'
  | 'field'
  | 'edu_start'
  | 'edu_end'
  | 'notice_period'
  | 'current_ctc'
  | 'expected_ctc'
  | 'relocation'
  | 'work_authorization'
  | 'why_this_role';

export type Fillable = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

/** One box on the form. `entry` is which job or school it belongs to (0 = first on the form). */
export type Field = { element: Fillable; kind: Kind; entry: number; label: string };

const TEXT_INPUTS = new Set(['', 'text', 'email', 'tel', 'url', 'number', 'date', 'month']);
// Never touched, whatever else the label says.
const OFF_LIMITS = /password|captcha|\botp\b|verification code|search|coupon|promo|user ?name|login/;

const BY_AUTOCOMPLETE: Record<string, Kind> = {
  'given-name': 'first_name',
  'family-name': 'last_name',
  name: 'full_name',
  email: 'email',
  tel: 'phone',
  'tel-national': 'phone',
  organization: 'company',
  'organization-title': 'title',
  'address-level2': 'location',
};

// Checked in order; the first that matches wins, so the specific come first.
const RULES: [Kind, RegExp][] = [
  ['email', /e-?mail/],
  ['phone', /phone|mobile|contact (?:no|number)|\btel\b|whats ?app/],
  ['first_name', /first name|given name|\bfname\b|forename/],
  ['last_name', /last name|surname|family name|\blname\b/],
  ['linkedin', /linked ?in/],
  ['github', /git ?hub/],
  ['portfolio', /portfolio|personal (?:web)?site|website|\bblog\b/],
  ['notice_period', /notice period|when can you (?:start|join)|earliest start|how soon can you/],
  ['expected_ctc', /expected (?:ctc|salary|compensation|pay)|salary expectation|desired (?:salary|compensation)/],
  ['current_ctc', /(?:current|present) (?:ctc|salary|compensation|pay)/],
  ['relocation', /relocat/],
  ['work_authorization', /work authori[sz]ation|authori[sz]ed to work|legally (?:authori[sz]ed|eligible)|right to work/],
  ['why_this_role', /why (?:do you want|are you interested|this (?:role|job|company|position)|us\b)|what interests you/],
  ['years', /years? of (?:\w+ )?experience|total experience|experience in years|\byoe\b/],
  ['school', /school|university|college|institut/],
  ['degree', /degree|qualification|level of education/],
  ['field', /field of study|\bmajor\b|speciali[sz]ation|discipline|\bbranch\b|\bstream\b/],
  ['edu_end', /graduation (?:year|date)|year of (?:passing|graduation|completion)|passing year/],
  ['company', /company|employer|organi[sz]ation/],
  ['title', /job title|(?:current|recent|previous|latest) (?:title|role|position|designation)|designation|(?:role|position) title|^title$/],
  ['job_description', /responsibilit|describe your (?:role|work)|role description|job description/],
  ['headline', /headline|professional title|tagline/],
  ['skills', /\bskills\b|technologies|tech stack/],
  ['location', /\bcity\b|location|where are you (?:based|located)|\btown\b|address/],
  ['full_name', /\bname\b/],
];

const START_DATE = /start (?:date|month|year)|^from$|^from (?:date|month|year)|date from|joining date/;
const END_DATE = /end (?:date|month|year)|^to$|^to (?:date|month|year)|date to|leaving date|^until$/;

const WORK_KINDS: ReadonlySet<Kind> = new Set(['company', 'title', 'job_start', 'job_end', 'job_description']);
const SCHOOL_KINDS: ReadonlySet<Kind> = new Set(['school', 'degree', 'field', 'edu_start', 'edu_end']);
const IDENTITY: ReadonlySet<Kind> = new Set(['first_name', 'last_name', 'full_name', 'email', 'phone']);
const APPLICATION_WORDS = /\bappl(?:y|ication)|\bcareers?\b|\bjobs?\b|\bresume\b|\bcv\b|recruit|hiring/i;

/** "firstName", "first_name" and "First Name *" all become "first name". */
function plain(text: string): string {
  return text
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_\-.[\]:*()/]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function textOf(doc: Document, ids: string | null): string {
  if (!ids) return '';
  return ids
    .split(/\s+/)
    .map((id) => doc.getElementById(id)?.textContent ?? '')
    .join(' ');
}

/** What the page calls this field, most trustworthy source first. */
function labelsOf(element: Fillable): string[] {
  const doc = element.ownerDocument;
  const visible = [
    ...[...(element.labels ?? [])].map((label) => label.textContent ?? ''),
    element.getAttribute('aria-label') ?? '',
    textOf(doc, element.getAttribute('aria-labelledby')),
    element.getAttribute('placeholder') ?? '',
  ];
  const internal = [element.getAttribute('name') ?? '', element.id, element.getAttribute('data-automation-id') ?? ''];
  return [...visible, ...internal].map(plain).filter((label) => label.length > 0 && label.length < 120);
}

function isOnScreen(element: HTMLElement): boolean {
  const box = element.getBoundingClientRect();
  if (box.width < 2 || box.height < 2) return false;
  // Boxes parked far off the page are traps for bots, not fields for people.
  if (box.right + window.scrollX < 0 || box.bottom + window.scrollY < 0) return false;
  const style = getComputedStyle(element);
  return style.visibility !== 'hidden' && style.opacity !== '0';
}

function usable(element: Element): element is Fillable {
  if (element.closest('rolesetu-root, [aria-hidden="true"]')) return false;
  if (element instanceof HTMLInputElement) {
    return TEXT_INPUTS.has(element.type) && !element.disabled && !element.readOnly;
  }
  if (element instanceof HTMLTextAreaElement) return !element.disabled && !element.readOnly;
  return element instanceof HTMLSelectElement && !element.disabled;
}

function kindOf(element: Fillable, labels: string[], section: 'work' | 'school' | null): Kind | null {
  if (labels.some((label) => OFF_LIMITS.test(label))) return null;

  const hint = BY_AUTOCOMPLETE[element.getAttribute('autocomplete')?.trim().toLowerCase() ?? ''];
  if (hint) return hint;
  if (element instanceof HTMLInputElement && element.type === 'email') return 'email';
  if (element instanceof HTMLInputElement && element.type === 'tel') return 'phone';

  // The label a person sees is tried in full before the next one, so
  // "Company name" is a company even though its id says "name".
  for (const label of labels) {
    // A date belongs to whichever job or school was named just before it.
    if (section && START_DATE.test(label)) return section === 'work' ? 'job_start' : 'edu_start';
    if (section && END_DATE.test(label)) return section === 'work' ? 'job_end' : 'edu_end';
    for (const [kind, pattern] of RULES) {
      if (!pattern.test(label)) continue;
      if (kind === 'job_description' && !(element instanceof HTMLTextAreaElement)) continue;
      return kind;
    }
  }
  return null;
}

/** Every field on the page we know how to fill, in the order it appears. */
export function findFields(doc: Document): Field[] {
  const fields: Field[] = [];
  let section: 'work' | 'school' | null = null;
  // Forms repeat a block per job and per school. A kind showing up again
  // means the next block has started.
  const entry = { work: -1, school: -1 };
  const seen = { work: new Set<Kind>(), school: new Set<Kind>() };

  for (const element of doc.querySelectorAll('input, textarea, select')) {
    if (!usable(element)) continue;
    const labels = labelsOf(element);
    if (labels.length === 0) continue;
    const kind = kindOf(element, labels, section);
    if (kind === null || !isOnScreen(element)) continue;

    let index = 0;
    const group = WORK_KINDS.has(kind) ? 'work' : SCHOOL_KINDS.has(kind) ? 'school' : null;
    if (group) {
      section = group;
      if (entry[group] === -1 || seen[group].has(kind)) {
        entry[group] += 1;
        seen[group].clear();
      }
      seen[group].add(kind);
      index = entry[group];
    }
    fields.push({ element, kind, entry: index, label: labels[0] ?? kind });
  }
  return fields;
}

/**
 * Whether the page holds a job application form, as opposed to a sign-up,
 * contact or checkout form. Cheap enough to run on every page.
 */
export function hasApplicationForm(doc: Document): boolean {
  if (doc.querySelectorAll('input, textarea, select').length < 2) return false;
  for (const password of doc.querySelectorAll('input[type="password"]')) {
    if (password instanceof HTMLElement && isOnScreen(password)) return false;
  }
  const kinds = new Set(findFields(doc).map((field) => field.kind));
  if (kinds.size < 2 || ![...kinds].some((kind) => IDENTITY.has(kind))) return false;

  // Name and email alone could be any form. Something has to say "job".
  const asksAboutWork = [...kinds].some((kind) => !IDENTITY.has(kind) && kind !== 'location');
  return (
    asksAboutWork ||
    doc.querySelector('input[type="file"]') !== null ||
    APPLICATION_WORDS.test(`${doc.title} ${doc.location?.pathname ?? ''}`)
  );
}
