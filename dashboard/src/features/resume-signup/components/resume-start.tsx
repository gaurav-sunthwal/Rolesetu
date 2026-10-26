'use client';

import { CircleAlert, LockKeyhole, Upload } from 'lucide-react';
import { useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { fileProblem, readResumeIdentity, type ResumeIdentity } from '@/features/resume/api';
import { errorMessage } from '@/lib/api/client';
import { cn } from '@/lib/utils';

export type ReadResume = { file: File; identity: ResumeIdentity };

/**
 * The first step of signing up with a resume: pick the PDF and read the email
 * off it. Only the email and first name come back; the file stays in the
 * browser until there is an account to save it to.
 */
export function ResumeStart({ onRead }: { onRead: (read: ReadResume) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [reading, setReading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function choose(file: File | undefined) {
    if (!file || reading) return;
    const issue = fileProblem(file);
    setProblem(issue);
    if (issue) return;
    setReading(true);
    try {
      onRead({ file, identity: await readResumeIdentity(file) });
    } catch (error) {
      setProblem(errorMessage(error));
    } finally {
      setReading(false);
      // Choosing the same file again after a problem should try again.
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        void choose(event.dataTransfer.files[0]);
      }}
      className={cn(
        'rounded-xl border border-dashed p-5 text-center transition-colors motion-reduce:transition-none',
        dragging && 'border-primary bg-primary/5',
      )}
    >
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        aria-label="Choose your resume PDF"
        onChange={(event) => void choose(event.target.files?.[0])}
      />
      <span className="bg-primary/10 text-primary mx-auto flex size-10 items-center justify-center rounded-full">
        <Upload className="size-4" />
      </span>
      <p className="mt-3 text-sm font-medium">Start with your resume</p>
      <p className="text-muted-foreground mt-1 text-xs">
        We fill in your profile from it, so there is nothing to type.
      </p>
      <Button
        size="lg"
        className="mt-4 h-10 w-full"
        onClick={() => input.current?.click()}
        disabled={reading}
        aria-busy={reading}
      >
        {reading ? (
          <>
            <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none" />
            Reading your resume…
          </>
        ) : (
          <>
            <Upload />
            Upload resume (PDF)
          </>
        )}
      </Button>
      <p className="text-muted-foreground mt-2 text-xs">or drag it here · up to 5 MB</p>

      {problem ? (
        <p
          role="alert"
          className="text-destructive mt-3 flex items-start gap-1.5 text-left text-xs"
        >
          <CircleAlert className="mt-px size-3.5 shrink-0" />
          {problem}
        </p>
      ) : null}

      <p className="text-muted-foreground mt-4 flex items-start gap-1.5 border-t pt-3 text-left text-xs">
        <LockKeyhole className="mt-px size-3.5 shrink-0" />
        Nothing is saved until you create your account. Your resume stays private.
      </p>
    </div>
  );
}
