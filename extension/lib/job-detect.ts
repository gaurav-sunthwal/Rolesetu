import { CONTROLS, hasApplyControl, isApplyControl } from './apply-controls';
import type { DetectedJob } from './messages';

const MIN_DESCRIPTION = 200;
const MAX_DESCRIPTION = 20000;
const JOB_CUE =
  /responsibilit|requirements?|qualifications?|what you(?:'ll| will)|about the (?:role|job)|skills? required|key skills|job description|we are looking for/i;

// Kinds of wording a job listing uses. A page must show two different kinds
// before its text alone is taken for a job.
const JOB_CUES = [
  /responsibilit/i,
  /requirements?|qualifications?|skills? required|key skills|must[- ]have/i,
  /what you(?:'ll| will)|about the (?:role|job|position)|job description|we are looking for|we're looking for/i,
  /years? of experience|\bfull[- ]time\b|\bpart[- ]time\b|\binternship\b|\bstipend\b|\bsalary\b|\bctc\b/i,
];

type Json = unknown;

function typesOf(node: Record<string, Json>): string[] {
  const kind = node['@type'];
  return Array.isArray(kind) ? kind.map(String) : [String(kind)];
}

function findPosting(data: Json): Record<string, Json> | null {
  if (Array.isArray(data)) {
    for (const item of data) {
      const found = findPosting(item);
      if (found) return found;
    }
    return null;
  }
  if (data && typeof data === 'object') {
    const node = data as Record<string, Json>;
    if (typesOf(node).includes('JobPosting')) return node;
    if ('@graph' in node) return findPosting(node['@graph']);
  }
  return null;
}

/** HTML to text with a line per block, using the browser's own parser. */
function htmlToText(markup: string): string {
  const holder = new DOMParser().parseFromString(markup, 'text/html').body;
  holder.querySelectorAll('br').forEach((node) => node.replaceWith('\n'));
  holder
    .querySelectorAll('p, li, div, h1, h2, h3, h4, tr')
    .forEach((node) => node.append('\n'));
  return tidy(holder.textContent ?? '');
}

function tidy(text: string): string {
  return text
    .split('\n')
    .map((line) => line.replace(/[ \t ]+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');
}

function text(value: Json): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** "Experience: ..." from the listing's own data, which may be text or a number of months. */
function experienceOf(value: Json): string | null {
  if (typeof value === 'string' && value.trim()) return `Experience: ${htmlToText(value)}`;
  if (value && typeof value === 'object') {
    const months = (value as Record<string, Json>).monthsOfExperience;
    if (typeof months === 'number' && months >= 0) {
      return months === 0
        ? 'No prior experience required.'
        : `${months} months of experience required.`;
    }
  }
  return null;
}

/** The job as the site itself describes it for search engines. */
function fromStructuredData(doc: Document): Omit<DetectedJob, 'url'> | null {
  for (const script of doc.querySelectorAll('script[type="application/ld+json"]')) {
    let data: Json;
    try {
      data = JSON.parse(script.textContent ?? '');
    } catch {
      continue;
    }
    const posting = findPosting(data);
    if (!posting) continue;

    let description = htmlToText(String(posting.description ?? ''));
    const skills = posting.skills;
    const skillList = Array.isArray(skills) ? skills.map(String).join(', ') : text(skills);
    if (skillList && !description.toLowerCase().includes(skillList.toLowerCase().slice(0, 40))) {
      description += `\n\nSkills required: ${skillList}`;
    }
    const experience = experienceOf(posting.experienceRequirements);
    if (experience && !description.includes(experience)) description += `\n\n${experience}`;
    if (description.length < MIN_DESCRIPTION) continue;

    const organisation = posting.hiringOrganization;
    const company =
      organisation && typeof organisation === 'object'
        ? text((organisation as Record<string, Json>).name)
        : text(organisation);
    return { title: text(posting.title), company, description };
  }
  return null;
}

// Where well-known sites put the job when they publish no structured data.
// Selectors match on part of a class name, because the full names change often.
const SITE_SELECTORS: { host: RegExp; title: string; company: string; description: string }[] = [
  {
    host: /linkedin\.com$/,
    title: '.job-details-jobs-unified-top-card__job-title, .top-card-layout__title',
    company:
      '.job-details-jobs-unified-top-card__company-name, .topcard__org-name-link, [class*="company-name"]',
    description:
      '#job-details, .jobs-description__content, .show-more-less-html__markup, .description__text',
  },
  {
    host: /naukri\.com$/,
    title: '[class*="jd-header-title"]',
    company: '[class*="jd-header-comp-name"] a, [class*="comp-name"]',
    description: '[class*="job-desc-container"], [class*="JDC__dang-inner-html"], [class*="job-desc"]',
  },
  {
    host: /indeed\.com$/,
    title: '[data-testid="jobsearch-JobInfoHeader-title"]',
    company: '[data-testid="inlineHeader-companyName"], [data-company-name]',
    description: '#jobDescriptionText',
  },
];

function visibleText(element: Element | null): string {
  return element instanceof HTMLElement ? tidy(element.innerText) : '';
}

const SECTION_HEADING =
  /^(?:about|full job description|job description|job details|job highlights|profile insights|description|responsibilit|requirement|qualification|overview|skills|benefits|meet the|how you match|your profile|people you can|show match|get personali[sz]ed)/i;

function firstLine(element: Element): string {
  return visibleText(element).split('\n')[0] ?? '';
}

function comesBefore(element: Element, other: Element): boolean {
  return (
    !element.contains(other) &&
    (element.compareDocumentPosition(other) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
  );
}

/**
 * The job's title, found from where the description sits instead of from class
 * names (which sites change constantly): walking outwards from the description,
 * the first pane that holds a large heading above it is the job's own pane, and
 * its largest heading is the title. Section headings ("About the job") are skipped.
 */
function titleNear(description: Element): string | null {
  let scope = description.parentElement;
  for (let depth = 0; scope && depth < 12; depth += 1, scope = scope.parentElement) {
    let best: { text: string; size: number } | null = null;
    const headings = scope.querySelectorAll(
      'h1, h2, h3, [role="heading"], [class*="title" i], a[href*="/jobs/view/"]',
    );
    for (const heading of headings) {
      if (!comesBefore(heading, description)) continue;
      const label = firstLine(heading);
      if (label.length < 3 || label.length > 140 || SECTION_HEADING.test(label)) continue;
      const size = Number.parseFloat(getComputedStyle(heading).fontSize);
      if (size >= 18 && (best === null || size > best.size)) best = { text: label, size };
    }
    if (best) return best.text;
  }
  return null;
}

/** The hiring company: the nearest link to a company page above the description. */
function companyNear(description: Element): string | null {
  let scope = description.parentElement;
  for (let depth = 0; scope && depth < 12; depth += 1, scope = scope.parentElement) {
    for (const link of scope.querySelectorAll('a[href*="/company/"], a[href*="/companies/"]')) {
      if (!comesBefore(link, description)) continue;
      const label = firstLine(link);
      if (label.length >= 2 && label.length <= 80) return label;
    }
  }
  return null;
}

/** "Title | Company | LinkedIn" in the browser tab, when the page is a single job. */
function fromTabTitle(doc: Document, host: string): { title: string; company: string } | null {
  if (!/linkedin\.com$/.test(host)) return null;
  const parts = doc.title
    .replace(/^\(\d+\+?\)\s*/, '')
    .split(' | ')
    .map((part) => part.trim());
  if (parts.length < 3 || /^jobs?$/i.test(parts[0] ?? '')) return null;
  return { title: parts[0] as string, company: parts[1] as string };
}

function describe(
  doc: Document,
  host: string,
  element: Element,
  selectors?: { title: string; company: string },
): Omit<DetectedJob, 'url'> {
  const tab = fromTabTitle(doc, host);
  const title =
    (selectors && visibleText(doc.querySelector(selectors.title)).split('\n')[0]) ||
    titleNear(element) ||
    tab?.title ||
    firstLine(doc.querySelector('h1') ?? doc.createElement('span')) ||
    null;
  const company =
    (selectors && visibleText(doc.querySelector(selectors.company)).split('\n')[0]) ||
    companyNear(element) ||
    tab?.company ||
    null;
  return { title, company, description: visibleText(element) };
}

// Text some sites add to a title for screen readers only ("React.js Developer - job post").
const TITLE_EXTRA = /\s*[-–|]\s*job post\s*$/i;
const NOT_A_COMPANY = /^(?:apply|save|share|report|follow|view|see|show|back|next|sign|log)\b/i;

function isShown(element: Element): boolean {
  if (!(element instanceof HTMLElement)) return false;
  const box = element.getBoundingClientRect();
  return box.width > 0 && box.height > 0;
}

/**
 * The job as the user sees it: the heading right above the page's Apply
 * button, and the company named between the two.
 *
 * This is what makes the title word for word what the page shows. A results
 * page lists many jobs and its hidden data can describe a different one, but
 * the Apply button belongs to the job the user is looking at.
 */
function byApplyButton(doc: Document): { title: string; company: string | null } | null {
  let button: Element | null = null;
  for (const control of doc.querySelectorAll(CONTROLS)) {
    if (isApplyControl(control) && isShown(control) && !control.closest('rolesetu-root')) {
      button = control;
      break;
    }
  }
  if (!button) return null;

  let scope = button.parentElement;
  for (let depth = 0; scope && depth < 10; depth += 1, scope = scope.parentElement) {
    let best: { element: Element; label: string; size: number } | null = null;
    for (const heading of scope.querySelectorAll('h1, h2, h3, [role="heading"]')) {
      if (!comesBefore(heading, button) || !isShown(heading)) continue;
      const label = firstLine(heading).replace(TITLE_EXTRA, '').trim();
      if (label.length < 3 || label.length > 140 || SECTION_HEADING.test(label)) continue;
      const size = Number.parseFloat(getComputedStyle(heading).fontSize);
      // The largest heading wins; between equals, the one nearest the button.
      if (size >= 16 && (best === null || size >= best.size)) best = { element: heading, label, size };
    }
    if (!best) continue;

    let company: string | null = null;
    const title = best.element;
    for (const candidate of scope.querySelectorAll(
      'a, [class*="company" i], [data-company-name], [data-testid*="company" i]',
    )) {
      if (!comesBefore(title, candidate) || !comesBefore(candidate, button)) continue;
      if (!isShown(candidate) || candidate.hasAttribute('data-rolesetu-pill')) continue;
      const label = firstLine(candidate);
      if (label.length < 2 || label.length > 80 || NOT_A_COMPANY.test(label)) continue;
      company = label;
      break;
    }
    return { title: best.label, company };
  }
  return null;
}

/** Whether these words can be read somewhere on the page. */
function appearsOnPage(doc: Document, words: string): boolean {
  const page = (doc.body?.innerText ?? '').replace(/\s+/g, ' ').toLowerCase();
  return page.includes(words.replace(/\s+/g, ' ').trim().toLowerCase());
}

function fromKnownSite(doc: Document, host: string): Omit<DetectedJob, 'url'> | null {
  const site = SITE_SELECTORS.find((entry) => entry.host.test(host));
  if (!site) return null;
  const element = doc.querySelector(site.description);
  if (!element || visibleText(element).length < MIN_DESCRIPTION) return null;
  return describe(doc, host, element, site);
}

/** Last resort: the block of the page that reads most like a job description. */
function fromPageText(
  doc: Document,
  host: string,
  strict: boolean,
): Omit<DetectedJob, 'url'> | null {
  const candidates = doc.querySelectorAll(
    '[class*="description" i], [id*="description" i], [class*="job-detail" i], [id*="job-detail" i], article, main',
  );
  let best: Element | null = null;
  let bestLength = 0;
  for (const element of candidates) {
    const length = visibleText(element).length;
    if (length > bestLength && length <= MAX_DESCRIPTION * 2) {
      best = element;
      bestLength = length;
    }
  }
  if (!best || bestLength < MIN_DESCRIPTION * 2) return null;
  const words = visibleText(best);
  if (!JOB_CUE.test(words)) return null;
  // Nobody asked for this page to be read, so an article that merely mentions
  // "requirements" must not pass: it has to read like a job and offer a way to apply.
  if (strict && (JOB_CUES.filter((cue) => cue.test(words)).length < 2 || !hasApplyControl(doc))) {
    return null;
  }
  return describe(doc, host, best);
}

/**
 * The job on this page, or null when the page is not a single job listing.
 *
 * `strict` is for pages checked without being asked: there, plain page text
 * needs stronger signs of a job than when the user pressed "Check this page".
 */
export function detectJob(doc: Document, url: string, strict = false): DetectedJob | null {
  const host = new URL(url).hostname.replace(/^www\./, '');

  // A site's hidden job data is the best source when it describes the job on
  // screen. On a results page it can be left over from another listing, and
  // then its title is nowhere to be seen: that data is ignored.
  let structured = fromStructuredData(doc);
  if (structured?.title && !appearsOnPage(doc, structured.title)) structured = null;

  const found = structured ?? fromKnownSite(doc, host) ?? fromPageText(doc, host, strict);
  if (!found) return null;

  // What is shown above the Apply button is what the user reads as the job's
  // title, so it is used word for word. Hidden data only fills in when the
  // page shows nothing there.
  const seen = byApplyButton(doc);
  const title = (structured?.title ?? seen?.title ?? found.title)?.replace(TITLE_EXTRA, '') ?? null;
  return {
    ...found,
    title,
    company: structured?.company ?? seen?.company ?? found.company,
    description: found.description.slice(0, MAX_DESCRIPTION),
    url,
  };
}
