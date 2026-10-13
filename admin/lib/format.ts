const dateTime = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
const date = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' });
const shortDay = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' });

export const formatDateTime = (iso: string | Date) => dateTime.format(new Date(iso));
export const formatDate = (iso: string | Date) => date.format(new Date(iso));
export const formatDay = (iso: string | Date) => shortDay.format(new Date(iso));

export function timeAgo(iso: string | Date) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}d ago`;
  return formatDate(iso);
}

export function formatBytes(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
