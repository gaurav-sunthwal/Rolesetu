/**
 * A birth date is saved once as YYYY-MM-DD, whatever form it was typed into,
 * and written back in the order each form asks for: 12/05/1998 on one site,
 * 05-12-1998 on the next.
 */

type Order = 'dmy' | 'mdy' | 'ymd';

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

// "DD/MM/YYYY", "mm-dd-yyyy", "YYYY.MM.DD", standing on their own.
const PATTERN =
  /(?:^|[^a-z])(d{1,2}|m{1,2}|y{2,4})([^a-z0-9]*)(?:d{1,2}|m{1,2}|y{2,4})[^a-z0-9]*(?:d{1,2}|m{1,2}|y{2,4})(?![a-z])/i;

/** The order the form shows, else the order this browser writes dates in. */
function orderOf(hint: string, locale: string): Order {
  const first = PATTERN.exec(hint)?.[1]?.[0]?.toLowerCase();
  if (first === 'y') return 'ymd';
  if (first === 'm') return 'mdy';
  if (first === 'd') return 'dmy';
  const parts = new Intl.DateTimeFormat(locale).formatToParts(new Date(2000, 10, 25));
  const order = parts.filter((part) => part.type !== 'literal').map((part) => part.type[0]);
  if (order[0] === 'y') return 'ymd';
  return order[0] === 'm' ? 'mdy' : 'dmy';
}

function separatorOf(hint: string): string {
  // "DD / MM / YYYY" is written with a plain slash.
  const between = PATTERN.exec(hint)?.[2] ?? '';
  const separator = between.trim() || between;
  return separator.length === 1 ? separator : '/';
}

function iso(year: number, month: number, day: number): string | null {
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null; // 31/02, or a month of 13
  }
  if (year < 1900 || date.getTime() > Date.now()) return null;
  return date.toISOString().slice(0, 10);
}

/**
 * Reads a whole birth date as the user typed it, or null when it is not one
 * (half typed, or a year on its own). `hint` is the field's label and placeholder.
 */
export function parseBirthDate(value: string, hint: string, locale: string): string | null {
  const tokens = value.toLowerCase().split(/[^0-9a-z]+/).filter(Boolean);
  if (tokens.length !== 3) return null;

  // "12 May 1998" and "May 12, 1998": the month is named, so there is no doubt.
  const named = tokens.findIndex((token) => /^[a-z]{3,}$/.test(token));
  if (named !== -1) {
    const month = MONTHS.indexOf(tokens[named]?.slice(0, 3) ?? '') + 1;
    const [day, year] = tokens.filter((_, index) => index !== named).map(Number);
    if (month === 0 || day === undefined || year === undefined || year < 1000) return null;
    return iso(year, month, day);
  }

  if (!tokens.every((token) => /^\d+$/.test(token))) return null;
  const [a = 0, b = 0, c = 0] = tokens.map(Number);
  if ((tokens[0]?.length ?? 0) === 4) return iso(a, b, c);
  if ((tokens[2]?.length ?? 0) !== 4) return null;
  // The numbers settle it when one of them cannot be a month.
  if (a > 12) return iso(c, b, a);
  if (b > 12) return iso(c, a, b);
  return orderOf(hint, locale) === 'mdy' ? iso(c, a, b) : iso(c, b, a);
}

/** The saved birth date written the way this field wants it. */
export function birthDateText(saved: string, hint: string, locale: string, type: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(saved);
  if (!match) return null;
  const [, year = '', month = '', day = ''] = match;
  if (type === 'date') return saved;
  const separator = separatorOf(hint);
  const order = orderOf(hint, locale);
  if (order === 'ymd') return [year, month, day].join(separator);
  if (order === 'mdy') return [month, day, year].join(separator);
  return [day, month, year].join(separator);
}
