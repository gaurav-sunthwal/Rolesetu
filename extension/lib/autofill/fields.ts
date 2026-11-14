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
  | 'why_this_role'
  | 'date_of_birth'
  | 'gender'
  | 'nationality'
  | 'postal_code'
  | 'heard_from'
  // Any other question the page labels. Its answer is learned from the user.
  | 'question';

export type Fillable = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

/**
 * One box on the form. `entry` is which job or school it belongs to (0 = first
 * on the form). `key` is where its saved answer lives: the kind for a question
 * we know, or one made from the words beside the box for any other. `question`
 * is those words, when a person can see them.
 */
export type Field = {
  element: Fillable;
  kind: Kind;
  entry: number;
  label: string;
  key: string;
  question: string | null;
};

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
  ['email', /\be ?mail/],
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
  ['date_of_birth', /date of birth|birth ?date|\bdob\b|\bd o b\b|born on/],
  ['gender', /\bgender\b|\bsex\b/],
  ['nationality', /nationality|citizenship/],
  ['postal_code', /postal|zip|pin ?code|postcode/],
  ['heard_from', /how did you (?:hear|find|learn|come across)|where did you (?:hear|find)|source of (?:application|hire)|referral source/],
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

/** A label's own words. One wrapped around a dropdown would otherwise include every option. */
function labelText(label: HTMLLabelElement): string {
  if (!label.querySelector('input, select, textarea')) return label.textContent ?? '';
  const copy = label.cloneNode(true) as HTMLLabelElement;
  copy.querySelectorAll('input, select, textarea').forEach((control) => control.remove());
  return copy.textContent ?? '';
}

function clean(labels: string[], longest = 120): string[] {
  return labels.map(plain).filter((label) => label.length > 0 && label.length < longest);
}

const CONTROLS = 'input, textarea, select';

export function isRadio(element: Element): element is HTMLInputElement {
  return element instanceof HTMLInputElement && element.type === 'radio';
}

/** The radios that answer the same question as `radio`. */
export function radioGroup(radio: HTMLInputElement): HTMLInputElement[] {
  if (!radio.name) return [radio];
  const scope = radio.form ?? radio.ownerDocument;
  return [...scope.querySelectorAll<HTMLInputElement>('input[type="radio"]')].filter(
    (other) => other.name === radio.name,
  );
}

/** The smallest box holding every option of a radio question (where its question sits above). */
export function radioBox(radio: HTMLInputElement): HTMLElement {
  const group = radioGroup(radio);
  let box: HTMLElement | null = radio.parentElement;
  while (box && !group.every((other) => box?.contains(other))) box = box.parentElement;
  return box ?? radio;
}

/** The words on a radio option ("Yes", "No, I need sponsorship"). */
export function radioText(radio: HTMLInputElement): string {
  const label = radio.labels?.[0];
  const text = label ? labelText(label) : (radio.nextSibling?.textContent ?? '');
  return (text.trim() || radio.getAttribute('aria-label') || radio.value).replace(/\s+/g, ' ').trim();
}

// Text near a field that is about the box, not the question. Tested on plain
// words, so "* This field is required" and "ⓘ This field is required" are caught.
const NOT_A_QUESTION =
  /^(?:\W*)(?:this (?:field|question) is required|this is a required (?:field|question)|required(?: field)?|optional|mandatory|please (?:fill|enter|select|answer)\b.*|\d+(?: \d+)?|\d+ (?:characters?|words?) (?:left|remaining|max).*|max(?:imum)? \d+.*)(?:\W*)$/;

/**
 * The words written above a field that has no label: many job sites (Internshala's
 * extra questions, assessment steps) put the question in a plain block above the
 * box. Climbs a few levels until a level has text before it, and stops at the
 * previous question's own box. Returns the blocks top first: the question, then
 * any hint under it.
 */
function questionAbove(start: Element): string[] {
  let node: Element | null = start;
  for (let depth = 0; node && depth < 5; depth += 1, node = node.parentElement) {
    if (node.tagName === 'FORM' || node === node.ownerDocument.body) break;
    const texts: string[] = [];
    for (let prev = node.previousElementSibling; prev; prev = prev.previousElementSibling) {
      if (prev.matches(CONTROLS) || prev.querySelector(CONTROLS)) break;
      if (prev instanceof HTMLElement && prev.hidden) continue;
      const text = (prev.textContent ?? '').replace(/\s+/g, ' ').trim();
      if (text && !NOT_A_QUESTION.test(plain(text))) texts.unshift(text);
    }
    if (texts.length > 0) return texts;
  }
  return [];
}

/** The words a person sees beside the field. */
function visibleLabelsOf(element: Fillable): string[] {
  const doc = element.ownerDocument;
  if (isRadio(element)) {
    // A radio's own label is an answer ("Yes"); the question is above the options.
    return clean(
      [
        element.closest('fieldset')?.querySelector('legend')?.textContent ?? '',
        textOf(doc, element.closest('[role="radiogroup"]')?.getAttribute('aria-labelledby') ?? null),
        ...questionAbove(radioBox(element)),
      ],
      300,
    );
  }
  const named = clean([
    ...[...(element.labels ?? [])].map(labelText),
    element.getAttribute('aria-label') ?? '',
    textOf(doc, element.getAttribute('aria-labelledby')),
  ]);
  // With a real label, a placeholder that is a whole sentence is an example answer
  // ("Hi! My name is Gaurav and..."), not what the box is: it would read as "name".
  if (named.length > 0) {
    const hint = clean([element.getAttribute('placeholder') ?? '']).filter((text) => text.split(' ').length <= 5);
    return [...named, ...hint];
  }
  // A placeholder that asks the question ("Your notice period") beats a heading above;
  // one that only says "Enter text ..." does not.
  const placeholder = clean([element.getAttribute('placeholder') ?? '']);
  const above = clean(questionAbove(element), 300);
  return placeholder.some((text) => !TOO_VAGUE.test(text))
    ? [...placeholder, ...above]
    : [...above, ...placeholder];
}

/** What the page calls this field, most trustworthy source first. */
function labelsOf(element: Fillable): string[] {
  const internal = [element.getAttribute('name') ?? '', element.id, element.getAttribute('data-automation-id') ?? ''];
  return [...visibleLabelsOf(element), ...clean(internal)];
}

function isOnScreen(element: HTMLElement): boolean {
  const box = element.getBoundingClientRect();
  if (box.width < 2 || box.height < 2) return false;
  // Boxes parked far off the page are traps for bots, not fields for people.
  if (box.right + window.scrollX < 0 || box.bottom + window.scrollY < 0) return false;
  const style = getComputedStyle(element);
  return style.visibility !== 'hidden' && style.opacity !== '0';
}

// Boxes for finding things on the site, not for answering an application.
// Not "find": "Where did you find this job?" is a real question.
const SEARCH_WORDS = /search|filter|keywords?\b|\bquery\b/i;

/**
 * A search box, filter or picker: the site's own tools for finding jobs. Never
 * filled, never learned from, and never offered AI.
 */
export function isSearchLike(element: Element): boolean {
  if (element instanceof HTMLInputElement && (element.type === 'search' || element.list !== null)) return true;
  if (element.closest('header, nav, [role="search"], [role="navigation"], [role="banner"], search')) return true;
  const role = element.getAttribute('role');
  if (role === 'searchbox' || role === 'combobox' || element.hasAttribute('aria-autocomplete')) return true;
  const words = [
    element.getAttribute('name'),
    element.id,
    element.getAttribute('placeholder'),
    element.getAttribute('aria-label'),
    element.getAttribute('type'),
    element.closest('form')?.getAttribute('action'),
  ].join(' ');
  return SEARCH_WORDS.test(words);
}

function usable(element: Element): element is Fillable {
  if (element.closest('rolesetu-root, [data-rolesetu-helpers], [aria-hidden="true"]')) return false;
  if (!(element instanceof HTMLSelectElement) && isSearchLike(element)) return false;
  if (isRadio(element)) return !element.disabled;
  if (element instanceof HTMLInputElement) {
    return TEXT_INPUTS.has(element.type) && !element.disabled && !element.readOnly;
  }
  if (element instanceof HTMLTextAreaElement) return !element.disabled && !element.readOnly;
  return element instanceof HTMLSelectElement && !element.disabled;
}

// Words that are part of a bigger question ("From", "Other"), not one on their own.
const TOO_VAGUE =
  /^(?:from|to|start|end|date|day|month|year|other|others|answer|response|select|choose|none|value|yes|no|comments?|message|notes?|details?|description|please specify|if (?:other|yes|so).*|type here.*|enter.*)$/;

/** A saved-answer key for a question we have no kind for: "q_" and its words. */
function questionKey(question: string): string {
  const words = question.replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  return `q_${words.slice(0, 56).replace(/_+$/, '')}`;
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
    const kinds = RULES.filter(
      ([kind, pattern]) =>
        pattern.test(label) && (kind !== 'job_description' || element instanceof HTMLTextAreaElement),
    ).map(([kind]) => kind);
    const [first] = kinds;
    if (first === undefined) continue;
    return isAskedInPassing(label, kinds, element) ? 'question' : first;
  }
  return 'question';
}

// A written question that only mentions a profile field on its way: "Describe a
// feature you built. Which tech stack did you use?" is not asking for the skills list.
const OPEN_ENDED =
  /^(?:describe|explain|tell|write|walk us|share (?:an?|your|any) (?:example|experience|story)|how (?:would|did|do) you|what (?:makes|motivates|excites|would))\b/;
const MENTIONED_IN_PASSING: ReadonlySet<Kind> = new Set<Kind>(['skills', 'location', 'headline']);
const PROFILE_KINDS_IN_QUESTIONS: ReadonlySet<Kind> = new Set<Kind>([...MENTIONED_IN_PASSING, 'job_description', 'years']);

/**
 * Whether a long question names a field without asking for just that field:
 * "What is your current CTC, expected CTC and notice period?" asks three things at
 * once, so it is one question with one written answer, not the notice period box.
 */
function isAskedInPassing(label: string, kinds: Kind[], element: Fillable): boolean {
  if (label.split(' ').length < 8) return false;
  if (new Set(kinds).size > 1) return true;
  const [kind] = kinds;
  if (kind === undefined) return false;
  if (MENTIONED_IN_PASSING.has(kind)) return true;
  // An essay box under an open question wants an answer in words, not a profile value.
  return OPEN_ENDED.test(label) && element instanceof HTMLTextAreaElement && PROFILE_KINDS_IN_QUESTIONS.has(kind);
}

/** What a person reads beside the box, if anything: a name like "input_17" says nothing. */
function visibleQuestion(element: Fillable): string | null {
  const question = visibleLabelsOf(element)[0];
  if (!question || question.length < 3 || TOO_VAGUE.test(question)) return null;
  if (!/[a-z]{2}/.test(question)) return null;
  // Long labels (e.g. Capgemini consent sentences) are valid questions — we just
  // truncate them to 100 chars for use as a key.  The full text is kept for display.
  return question;
}

/** Stable key for any question text, including long consent/policy sentences. */
function questionKeyOf(question: string): string {
  // Truncate to first 100 chars before normalising, so long sentences still
  // produce a key that is stable across the same question on different pages.
  const truncated = question.slice(0, 100);
  return questionKey(truncated);
}

/** The saved-answer key for a question as a person reads it ("Notice period *"). */
export function keyForQuestion(text: string): string {
  return questionKeyOf(plain(text));
}

/** Every field on the page we know how to fill, in the order it appears. */
export function findFields(doc: Document): Field[] {
  const fields: Field[] = [];
  let section: 'work' | 'school' | null = null;
  // Forms repeat a block per job and per school. A kind showing up again
  // means the next block has started.
  const entry = { work: -1, school: -1 };
  const seen = { work: new Set<Kind>(), school: new Set<Kind>() };
  // A radio question is one field, however many options it has.
  const radioNames = new Set<string>();

  for (const element of doc.querySelectorAll('input, textarea, select')) {
    if (!usable(element)) continue;
    if (isRadio(element) && element.name) {
      if (radioNames.has(element.name)) continue;
      radioNames.add(element.name);
    }
    const labels = labelsOf(element);
    if (labels.length === 0) continue;
    const kind = kindOf(element, labels, section);
    // Sites often hide the real radio and draw their own: what shows is the options' box.
    const shown = isRadio(element) ? isOnScreen(element) || isOnScreen(radioBox(element)) : isOnScreen(element);
    if (kind === null || !shown) continue;

    let key: string = kind;
    const question = visibleQuestion(element);
    if (kind === 'question') {
      if (question !== null) {
        key = questionKeyOf(question);
      } else if (element instanceof HTMLSelectElement) {
        // Consent / EEO dropdowns often have no readable label but are still
        // worth remembering per-site.  Use the element's name or id as key.
        const fallback = element.getAttribute('name') || element.id;
        if (!fallback) continue;
        key = `q_${fallback.replace(/[^a-z0-9]+/gi, '_').toLowerCase().slice(0, 56)}`;
      } else {
        // A text input with no readable label can't be matched next time.
        continue;
      }
    }

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
    fields.push({ element, kind, entry: index, label: labels[0] ?? kind, key, question });
  }
  return fields;
}

const BOXES = '[role="dialog"], dialog[open], [aria-modal="true"], form';
// Words only an application uses about itself: "Apply to", "Your application",
// "Send application". Not a bare "apply": a checkout says "Apply coupon".
const APPLYING_WORDS =
  /\bapply (?:to|for|now)\b|\b(?:your|send|submit|job) application\b|\bsubmit (?:your )?application\b|\bcover letter\b|\b(?:upload|attach) (?:your )?(?:resume|cv)\b|\breach out to the team\b/i;

/** Whether an open pop-up, or a form, on the page says it is for applying. */
function boxSaysApply(doc: Document): boolean {
  for (const box of doc.querySelectorAll(BOXES)) {
    if (!(box instanceof HTMLElement) || !isOnScreen(box)) continue;
    if (!box.querySelector('textarea, input:not([type="hidden"]), select')) continue;
    if (APPLYING_WORDS.test((box.textContent ?? '').slice(0, 4000))) return true;
  }
  return false;
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

  // An "Apply" pop-up or form on a page that is not about one job (a company's page
  // on Wellfound): its own words say what it is, whatever the address says.
  if (boxSaysApply(doc) && findFields(doc).length > 0) return true;

  // Multi-step career portals (e.g. Capgemini) show only consent/EEO dropdowns
  // on the final step — no name or email field is visible.  Trust the URL if it
  // clearly says this is a career page, so learning still fires on late steps.
  if (APPLICATION_WORDS.test(`${doc.title} ${doc.location?.pathname ?? ''}`)) {
    // Still require at least one visible, fillable select or input on the page.
    const fields = findFields(doc);
    if (fields.length > 0) return true;
  }

  // An unknown question is in every kind of form, so it says nothing about this one.
  const kinds = new Set(
    findFields(doc)
      .map((field) => field.kind)
      .filter((kind) => kind !== 'question'),
  );
  if (kinds.size < 2 || ![...kinds].some((kind) => IDENTITY.has(kind))) return false;

  // Name and email alone could be any form. Something has to say "job".
  const asksAboutWork = [...kinds].some((kind) => !IDENTITY.has(kind) && kind !== 'location');
  return (
    asksAboutWork ||
    doc.querySelector('input[type="file"]') !== null ||
    APPLICATION_WORDS.test(`${doc.title} ${doc.location?.pathname ?? ''}`)
  );
}
