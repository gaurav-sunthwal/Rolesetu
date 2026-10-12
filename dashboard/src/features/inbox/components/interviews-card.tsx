'use client';

import { CalendarClock, CalendarPlus, Download, MapPin, Pencil, Trash2, Video } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { SectionCard } from '@/components/app/section-card';
import { EmptyState, ErrorState } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import type { Interview } from '@/features/inbox/api';
import { calendarFile, googleCalendarUrl, titleOf } from '@/features/inbox/calendar';
import { useDeleteInterview, useInterviews, useUpdateInterview } from '@/features/inbox/hooks';
import { errorMessage } from '@/lib/api/client';
import { cn } from '@/lib/utils';

const LENGTHS = [30, 45, 60, 90] as const;

function dayLabel(interview: Interview): string {
  if (!interview.starts_at) return 'Time not set';
  const start = new Date(interview.starts_at);
  // A day-only interview is stored as midnight UTC, so it is shown in UTC to keep the day right.
  const day = start.toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    ...(interview.has_time ? {} : { timeZone: 'UTC' }),
  });
  if (!interview.has_time) return `${day} · time not given`;
  const time = (date: Date) =>
    date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  const end = interview.ends_at ? ` – ${time(new Date(interview.ends_at))}` : '';
  return `${day} · ${time(start)}${end}`;
}

function countdown(interview: Interview, now: number): string | null {
  if (!interview.starts_at || !interview.has_time) return null;
  const minutes = Math.round((new Date(interview.starts_at).getTime() - now) / 60000);
  if (minutes < 0) return null;
  if (minutes < 60) return `in ${minutes} min`;
  if (minutes < 48 * 60) return `in ${Math.round(minutes / 60)} hours`;
  return `in ${Math.round(minutes / (60 * 24))} days`;
}

/**
 * Interviews found in the user's mail: when, where, and a way to put each on
 * their calendar. Ones whose time could not be read ask for it instead of guessing.
 */
export function InterviewsCard({ hideWhenEmpty = false }: { hideWhenEmpty?: boolean }) {
  const interviews = useInterviews();
  const [editing, setEditing] = useState<Interview | null>(null);
  const [removing, setRemoving] = useState<Interview | null>(null);
  const [showPast, setShowPast] = useState(false);
  const remove = useDeleteInterview();
  // Read once per render pass of this card; precise to the minute is enough here.
  const [now] = useState(() => Date.now());

  if (interviews.isPending) {
    return hideWhenEmpty ? null : <Skeleton className="h-40 w-full rounded-3xl" />;
  }
  if (interviews.isError) {
    if (hideWhenEmpty) return null;
    return (
      <SectionCard title="Interviews">
        <ErrorState error={interviews.error} onRetry={() => void interviews.refetch()} />
      </SectionCard>
    );
  }

  const isPast = (interview: Interview) =>
    interview.starts_at !== null &&
    new Date(interview.ends_at ?? interview.starts_at).getTime() <
      now - (interview.has_time ? 0 : 24 * 60 * 60 * 1000);
  const upcoming = interviews.data.filter((interview) => !isPast(interview));
  const past = interviews.data.filter(isPast).reverse();
  if (hideWhenEmpty && upcoming.length === 0) return null;

  return (
    <SectionCard
      title="Interviews"
      description="Read from your interview mails. Check each time against the mail before you rely on it."
    >
      {upcoming.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title="No interviews coming up"
          body="When an interview invitation arrives in your Gmail, it shows up here with its date, time and meeting link."
          className="py-6"
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {upcoming.map((interview) => (
            <InterviewRow
              key={interview.id}
              interview={interview}
              soon={countdown(interview, now)}
              onEdit={() => setEditing(interview)}
              onRemove={() => setRemoving(interview)}
            />
          ))}
        </ul>
      )}

      {past.length > 0 ? (
        <div className="mt-4">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-sm font-medium"
            aria-expanded={showPast}
            onClick={() => setShowPast(!showPast)}
          >
            {showPast ? 'Hide' : 'Show'} {past.length} past{' '}
            {past.length === 1 ? 'interview' : 'interviews'}
          </button>
          {showPast ? (
            <ul className="mt-3 flex flex-col gap-3">
              {past.map((interview) => (
                <InterviewRow
                  key={interview.id}
                  interview={interview}
                  soon={null}
                  past
                  onEdit={() => setEditing(interview)}
                  onRemove={() => setRemoving(interview)}
                />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="rounded-3xl p-6 sm:max-w-md">
          {editing ? (
            <EditForm key={editing.id} interview={editing} onDone={() => setEditing(null)} />
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title="Remove this interview?"
        description="It is taken off this list. Your application and your mail are not affected."
        confirmLabel="Remove"
        pending={remove.isPending}
        onConfirm={() => {
          if (!removing) return;
          remove.mutate(removing.id, {
            onSuccess: () => {
              setRemoving(null);
              toast.success('Interview removed');
            },
            onError: (error) => toast.error(errorMessage(error)),
          });
        }}
      />
    </SectionCard>
  );
}

function InterviewRow({
  interview,
  soon,
  past,
  onEdit,
  onRemove,
}: {
  interview: Interview;
  soon: string | null;
  past?: boolean;
  onEdit: () => void;
  onRemove: () => void;
}) {
  const google = googleCalendarUrl(interview);
  const needsTime = !interview.starts_at || !interview.has_time;

  function download() {
    const file = calendarFile(interview);
    if (!file) return;
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = file.name;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <li className={cn('rounded-2xl border p-4', past && 'opacity-70')}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <p className="font-semibold">{titleOf(interview).replace(/^Interview: /, '')}</p>
          <p className={cn('mt-0.5 text-sm', needsTime ? 'text-warning font-medium' : '')}>
            {dayLabel(interview)}
            {soon ? <span className="text-primary font-medium"> · {soon}</span> : null}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button variant="ghost" size="icon" aria-label="Edit interview" onClick={onEdit}>
            <Pencil />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Remove interview" onClick={onRemove}>
            <Trash2 />
          </Button>
        </div>
      </div>

      {interview.location ? (
        <p className="text-muted-foreground mt-2 flex items-center gap-1.5 text-sm">
          <MapPin className="size-3.5 shrink-0" />
          {interview.location}
        </p>
      ) : null}
      {interview.mail_subject ? (
        <p className="text-muted-foreground mt-2 text-xs">
          From the mail: “{interview.mail_subject}”
          {interview.gmail_url ? (
            <>
              {' · '}
              <a
                href={interview.gmail_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline-offset-4 hover:underline"
              >
                Open in Gmail
              </a>
            </>
          ) : null}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {interview.link ? (
          <Button
            size="sm"
            nativeButton={false}
            render={<a href={interview.link} target="_blank" rel="noreferrer" />}
          >
            <Video />
            {/calendly\.com|cal\.com/.test(interview.link) ? 'Choose a slot' : 'Join meeting'}
          </Button>
        ) : null}
        {needsTime && !past ? (
          <Button size="sm" variant="outline" onClick={onEdit}>
            <CalendarClock />
            Set date and time
          </Button>
        ) : null}
        {google && !past ? (
          <>
            <Button
              size="sm"
              variant="outline"
              nativeButton={false}
              render={<a href={google} target="_blank" rel="noreferrer" />}
            >
              <CalendarPlus />
              Add to Google Calendar
            </Button>
            <Button size="sm" variant="ghost" onClick={download}>
              <Download />
              Calendar file
            </Button>
          </>
        ) : null}
      </div>
    </li>
  );
}

/** "2026-10-14" and "15:00" in the user's own timezone, for the date and time inputs. */
function localParts(iso: string | null, hasTime: boolean): { date: string; time: string } {
  if (!iso) return { date: '', time: '' };
  const moment = new Date(iso);
  if (!hasTime) return { date: iso.slice(0, 10), time: '' };
  const pad = (value: number) => String(value).padStart(2, '0');
  return {
    date: `${moment.getFullYear()}-${pad(moment.getMonth() + 1)}-${pad(moment.getDate())}`,
    time: `${pad(moment.getHours())}:${pad(moment.getMinutes())}`,
  };
}

function EditForm({ interview, onDone }: { interview: Interview; onDone: () => void }) {
  const update = useUpdateInterview();
  const initial = localParts(interview.starts_at, interview.has_time);
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [minutes, setMinutes] = useState<number>(() => {
    if (!interview.starts_at || !interview.ends_at) return 45;
    const length =
      (new Date(interview.ends_at).getTime() - new Date(interview.starts_at).getTime()) / 60000;
    return LENGTHS.find((option) => option === length) ?? 45;
  });
  const [link, setLink] = useState(interview.link ?? '');
  const [location, setLocation] = useState(interview.location ?? '');

  function save(event: FormEvent) {
    event.preventDefault();
    // Read in the user's own timezone, sent as an exact moment.
    const start = new Date(`${date}T${time}`);
    update.mutate(
      {
        id: interview.id,
        body: {
          starts_at: start.toISOString(),
          ends_at: new Date(start.getTime() + minutes * 60000).toISOString(),
          link,
          location,
        },
      },
      {
        onSuccess: () => {
          toast.success('Interview updated');
          onDone();
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  const field = 'flex flex-col gap-1.5';
  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{titleOf(interview)}</DialogTitle>
        <DialogDescription>
          Set what the mail says. Times are in your own timezone. A time you set here is not changed
          by later mails.
        </DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-2 gap-3">
        <div className={field}>
          <Label htmlFor="interview-date">Date</Label>
          <Input
            id="interview-date"
            type="date"
            required
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </div>
        <div className={field}>
          <Label htmlFor="interview-time">Time</Label>
          <Input
            id="interview-time"
            type="time"
            required
            value={time}
            onChange={(event) => setTime(event.target.value)}
          />
        </div>
      </div>
      <div className={field}>
        <Label htmlFor="interview-length">Length</Label>
        <select
          id="interview-length"
          value={minutes}
          onChange={(event) => setMinutes(Number(event.target.value))}
          className="border-input bg-background h-9 rounded-full border px-3 text-sm"
        >
          {LENGTHS.map((option) => (
            <option key={option} value={option}>
              {option} minutes
            </option>
          ))}
        </select>
      </div>
      <div className={field}>
        <Label htmlFor="interview-link">Meeting link</Label>
        <Input
          id="interview-link"
          type="url"
          placeholder="https://meet.google.com/…"
          value={link}
          onChange={(event) => setLink(event.target.value)}
        />
      </div>
      <div className={field}>
        <Label htmlFor="interview-location">Place</Label>
        <Input
          id="interview-location"
          placeholder="Office address, if it is in person"
          maxLength={200}
          value={location}
          onChange={(event) => setLocation(event.target.value)}
        />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" disabled={update.isPending} onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={update.isPending || !date || !time}>
          {update.isPending ? 'Saving…' : 'Save'}
        </Button>
      </DialogFooter>
    </form>
  );
}
