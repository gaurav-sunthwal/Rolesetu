import { format, formatDistanceToNowStrict } from 'date-fns';

export function formatDate(iso: string): string {
  return format(new Date(iso), 'd MMM yyyy');
}

export function timeAgo(iso: string): string {
  return formatDistanceToNowStrict(new Date(iso), { addSuffix: true });
}

/** 'YYYY-MM' -> 'Jan 2024'. */
export function formatMonth(yearMonth: string): string {
  return format(new Date(`${yearMonth}-01T00:00:00`), 'MMM yyyy');
}

export function newId(): string {
  return crypto.randomUUID();
}
