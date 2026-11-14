/** Describing the browser in the short plain words the server accepts. */

/** Only letters, digits and a few separators: what the server accepts. */
export function plain(value: string | undefined, max: number, allowed = /[^\w .()/-]/g): string | undefined {
  const cleaned = value?.replace(allowed, '').trim().slice(0, max);
  return cleaned ? cleaned : undefined;
}

export type Brand = { brand: string; version: string };

/** "Google Chrome 142", "Microsoft Edge 142", "Brave 142", "Firefox". */
export function browserName(brands: Brand[] | undefined, userAgent: string): string | undefined {
  if (brands && brands.length > 0) {
    const named = brands.filter((b) => !/not.?a.?brand/i.test(b.brand));
    const best = named.find((b) => b.brand !== 'Chromium') ?? named[0];
    if (best) return plain(`${best.brand} ${best.version}`, 40);
  }
  const firefox = /Firefox\/(\d+)/.exec(userAgent);
  return firefox ? `Firefox ${firefox[1]}` : undefined;
}
