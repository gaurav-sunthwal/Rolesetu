'use client';

import { CircleAlert, ExternalLink, FileText, Trash2, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  type ApplyMode,
  getResumeDownloadLink,
  MAX_RESUME_BYTES,
  type Resume,
} from '@/features/resume/api';
import {
  useApplyResume,
  useDeleteResume,
  useLatestResume,
  useUploadResume,
} from '@/features/resume/hooks';
import { errorMessage } from '@/lib/api/client';
import type { Profile } from '@/lib/api/types';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

function isEmpty(profile: Profile): boolean {
  return (
    !profile.full_name &&
    !profile.headline &&
    profile.skills.length + profile.experience.length === 0 &&
    profile.projects.length + profile.education.length === 0
  );
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function summaryOf(parsed: NonNullable<Resume['parsed']>): string {
  return [
    plural(parsed.skills?.length ?? 0, 'skill', 'skills'),
    plural(parsed.experience?.length ?? 0, 'role', 'roles'),
    plural(parsed.projects?.length ?? 0, 'project', 'projects'),
    plural(parsed.education?.length ?? 0, 'education entry', 'education entries'),
  ].join(' · ');
}

function fileProblem(file: File): string | null {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    return 'That is not a PDF. Export your resume as a PDF and upload that.';
  }
  if (file.size > MAX_RESUME_BYTES) return 'That file is larger than 5 MB. Export a smaller PDF.';
  if (file.size === 0) return 'That file is empty. Choose your resume PDF and try again.';
  return null;
}

/**
 * Upload a resume and have the profile filled from it. `onApplied` fires after
 * the profile changes, so forms holding their own copy of it can reset.
 */
export function ResumeCard({ profile, onApplied }: { profile: Profile; onApplied: () => void }) {
  const resume = useLatestResume();
  const upload = useUploadResume();
  const apply = useApplyResume();
  const remove = useDeleteResume();

  const input = useRef<HTMLInputElement>(null);
  const autoApplied = useRef<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<'replace' | 'delete' | null>(null);

  const current = resume.data ?? null;
  const applyMutate = apply.mutate;

  function runApply(id: string, mode: ApplyMode, parsed: NonNullable<Resume['parsed']>) {
    applyMutate(
      { id, mode },
      {
        onSuccess: () => {
          toast.success(`Profile filled from your resume: ${summaryOf(parsed)}`);
          setConfirming(null);
          onApplied();
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  // Nothing on the profile yet: there is nothing to overwrite, so fill it
  // straight away instead of asking. Once per resume.
  const readyToAutoApply =
    current?.status === 'parsed' && !current.applied_at && current.parsed && isEmpty(profile);
  useEffect(() => {
    if (!readyToAutoApply || !current?.parsed || autoApplied.current === current.id) return;
    autoApplied.current = current.id;
    const parsed = current.parsed;
    applyMutate(
      { id: current.id, mode: 'merge' },
      {
        onSuccess: () => {
          toast.success(`Profile filled from your resume: ${summaryOf(parsed)}`);
          onApplied();
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }, [readyToAutoApply, current, applyMutate, onApplied]);

  function choose(file: File | undefined) {
    if (!file) return;
    const issue = fileProblem(file);
    setProblem(issue);
    if (issue) return;
    upload.mutate(file, { onError: (error) => setProblem(errorMessage(error)) });
  }

  async function view(id: string) {
    // Opened before the request so the browser treats it as a user action.
    const tab = window.open('', '_blank');
    try {
      const url = await getResumeDownloadLink(id);
      if (tab) tab.location.href = url;
      else window.location.href = url;
    } catch (error) {
      tab?.close();
      toast.error(errorMessage(error));
    }
  }

  const picker = (
    <input
      ref={input}
      type="file"
      accept="application/pdf,.pdf"
      className="sr-only"
      aria-label="Resume PDF"
      onChange={(event) => {
        choose(event.target.files?.[0]);
        event.target.value = '';
      }}
    />
  );

  if (resume.isPending) return <Skeleton className="h-36 rounded-3xl" />;

  const busy = upload.isPending || apply.isPending;
  if (busy) {
    const label = !upload.isPending
      ? 'Filling in your profile…'
      : upload.progress < 1
        ? `Uploading… ${Math.round(upload.progress * 100)}%`
        : 'Reading your resume…';
    return (
      <section aria-live="polite" className="bg-card rounded-3xl border p-6">
        <div className="flex items-center gap-4">
          <div className="border-secondary border-t-primary size-9 shrink-0 animate-spin rounded-full border-4 motion-reduce:animate-none" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{label}</p>
            <p className="text-muted-foreground text-sm">This takes a few seconds.</p>
          </div>
        </div>
        {upload.isPending ? (
          <div className="bg-secondary mt-4 h-1.5 overflow-hidden rounded-full">
            <div
              className="bg-primary h-full rounded-full transition-[width] motion-reduce:transition-none"
              style={{ width: `${Math.round(upload.progress * 100)}%` }}
            />
          </div>
        ) : null}
      </section>
    );
  }

  // A resume is on file and has been read.
  if (current && current.status === 'parsed' && current.parsed) {
    const parsed = current.parsed;
    const applied = current.applied_at !== null;
    return (
      <section className="bg-card rounded-3xl border p-5 sm:p-6">
        {picker}
        <div className="flex flex-wrap items-center gap-4">
          <span className="bg-primary/10 text-primary flex size-11 shrink-0 items-center justify-center rounded-full">
            <FileText className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{current.filename}</p>
            <p className="text-muted-foreground text-sm">
              {applied && current.applied_at
                ? `Added to your profile on ${formatDate(current.applied_at)}`
                : `Found ${summaryOf(parsed)}`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => view(current.id)}>
              <ExternalLink />
              View
            </Button>
            <Button variant="ghost" size="sm" onClick={() => input.current?.click()}>
              <Upload />
              Upload new
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Delete resume file"
              className="text-muted-foreground hover:text-destructive"
              onClick={() => setConfirming('delete')}
            >
              <Trash2 />
            </Button>
          </div>
        </div>

        {applied ? null : (
          <div className="bg-secondary/60 mt-4 rounded-2xl p-4">
            <p className="text-sm font-medium">
              Your profile already has details. What should happen?
            </p>
            <p className="text-muted-foreground mt-1 text-sm">
              Adding keeps everything you have and fills in what is missing. Replacing swaps your
              whole profile for what is in this resume.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => runApply(current.id, 'merge', parsed)}>
                Add to my profile
              </Button>
              <Button variant="outline" onClick={() => setConfirming('replace')}>
                Replace my profile
              </Button>
            </div>
          </div>
        )}
        {problem ? <Problem>{problem}</Problem> : null}

        <ConfirmDialog
          open={confirming === 'replace'}
          onOpenChange={(open) => !open && setConfirming(null)}
          title="Replace your whole profile?"
          description="Everything on your profile now, including edits you made by hand, will be replaced with what is in this resume. This cannot be undone."
          confirmLabel="Replace profile"
          pending={apply.isPending}
          onConfirm={() => runApply(current.id, 'replace', parsed)}
        />
        <ConfirmDialog
          open={confirming === 'delete'}
          onOpenChange={(open) => !open && setConfirming(null)}
          title="Delete this resume file?"
          description="The PDF is removed from storage. Your profile stays exactly as it is."
          confirmLabel={remove.isPending ? 'Deleting…' : 'Delete file'}
          pending={remove.isPending}
          onConfirm={() =>
            remove.mutate(current.id, {
              onSuccess: () => {
                setConfirming(null);
                toast.success('Resume file deleted');
              },
              onError: (error) => toast.error(errorMessage(error)),
            })
          }
        />
      </section>
    );
  }

  // No resume on file yet.
  return (
    <section
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        choose(event.dataTransfer.files[0]);
      }}
      className={cn(
        'bg-card rounded-3xl border border-dashed p-6 text-center transition-colors sm:p-8',
        dragging && 'border-primary bg-primary/5',
      )}
    >
      {picker}
      <span className="bg-primary/10 text-primary mx-auto flex size-12 items-center justify-center rounded-full">
        <Upload className="size-5" />
      </span>
      <h2 className="mt-4 text-lg font-semibold">Upload your resume</h2>
      <p className="text-muted-foreground mx-auto mt-1 max-w-md text-sm">
        We read your PDF and fill in your skills, roles, projects and education for you. You can
        correct anything afterwards.
      </p>
      <Button className="mt-5" onClick={() => input.current?.click()}>
        <Upload />
        Choose PDF
      </Button>
      <p className="text-muted-foreground mt-3 text-xs">or drag it here · PDF up to 5 MB</p>
      {problem ? <Problem>{problem}</Problem> : null}
    </section>
  );
}

function Problem({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      className="bg-destructive/10 text-destructive mt-4 flex items-start gap-2 rounded-2xl px-4 py-3 text-left text-sm"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" />
      {children}
    </p>
  );
}
