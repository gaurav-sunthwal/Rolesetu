import type { Interview } from '@/features/inbox/api';

/** Used when the mail gave a start but no end. */
const DEFAULT_MINUTES = 45;
const DAY_MS = 24 * 60 * 60 * 1000;

export function titleOf(interview: Interview): string {
  const what = [interview.role, interview.company].filter(Boolean).join(' at ');
  return what ? `Interview: ${what}` : 'Interview';
}

function detailsOf(interview: Interview): string {
  return [interview.link ? `Join: ${interview.link}` : null, interview.notes, 'Added from Rolesetu']
    .filter(Boolean)
    .join('\n');
}

/** 20261014T093000Z, the form calendars expect for a moment in time. */
function stamp(date: Date): string {
  return date.toISOString().replace(/[-:]|\.\d{3}/g, '');
}

/** The start and end as calendar text: exact moments, or whole days when only the day is known. */
function span(interview: Interview): { start: string; end: string; allDay: boolean } | null {
  if (!interview.starts_at) return null;
  const start = new Date(interview.starts_at);
  if (!interview.has_time) {
    // Stored as midnight UTC of the day, so the day is read in UTC too.
    const day = (date: Date) => date.toISOString().slice(0, 10).replace(/-/g, '');
    return { start: day(start), end: day(new Date(start.getTime() + DAY_MS)), allDay: true };
  }
  const end = interview.ends_at
    ? new Date(interview.ends_at)
    : new Date(start.getTime() + DEFAULT_MINUTES * 60 * 1000);
  return { start: stamp(start), end: stamp(end), allDay: false };
}

/** A link that opens Google Calendar with the event filled in. Needs no extra permission. */
export function googleCalendarUrl(interview: Interview): string | null {
  const when = span(interview);
  if (!when) return null;
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: titleOf(interview),
    dates: `${when.start}/${when.end}`,
    details: detailsOf(interview),
    location: interview.location ?? interview.link ?? '',
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function escapeText(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/([,;])/g, '\\$1');
}

/** A calendar file that Apple Calendar, Outlook and others can open. */
export function calendarFile(interview: Interview): File | null {
  const when = span(interview);
  if (!when) return null;
  const kind = when.allDay ? ';VALUE=DATE' : '';
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Rolesetu//Interviews//EN',
    'BEGIN:VEVENT',
    `UID:${interview.id}@rolesetu`,
    `DTSTAMP:${stamp(new Date())}`,
    `DTSTART${kind}:${when.start}`,
    `DTEND${kind}:${when.end}`,
    `SUMMARY:${escapeText(titleOf(interview))}`,
    `DESCRIPTION:${escapeText(detailsOf(interview))}`,
    `LOCATION:${escapeText(interview.location ?? interview.link ?? '')}`,
    // A reminder half an hour before.
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    'DESCRIPTION:Interview soon',
    'TRIGGER:-PT30M',
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ];
  return new File([lines.join('\r\n')], 'interview.ics', { type: 'text/calendar' });
}
