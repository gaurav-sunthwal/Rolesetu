'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

type Changes = Record<string, string | null>;

/**
 * Changes several filters in the address in one step. Two separate changes in
 * a row would each start from the same old address, and the second would undo
 * the first, so filters that change together must go through this.
 */
export function useSetUrlFilters(): (changes: Changes) => void {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  return (changes: Changes) => {
    const next = new URLSearchParams(params.toString());
    for (const [name, value] of Object.entries(changes)) {
      if (value) next.set(name, value);
      else next.delete(name);
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };
}

/**
 * A filter kept in the address (`?name=value`), so a link from the dashboard
 * opens a page already filtered, and the filter survives a reload.
 */
export function useUrlFilter(name: string): [string | null, (value: string | null) => void] {
  const params = useSearchParams();
  const setFilters = useSetUrlFilters();
  return [params.get(name), (value) => setFilters({ [name]: value })];
}
