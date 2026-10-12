'use client';

import { CircleAlert, CircleCheck, Download, Loader2, Save } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import {
  type AddedSkill,
  type TailoredResume,
  type TailorRequest,
  toPdfFile,
} from '@/features/tailoring/api';
import { useKeepTailoredResume } from '@/features/tailoring/hooks';
import { errorMessage } from '@/lib/api/client';
import { cn } from '@/lib/utils';

type View = 'after' | 'before';

export function TailorPreviewDialog({
  tailored,
  request,
  moving,
  onMove,
  onClose,
}: {
  tailored: TailoredResume | null;
  /** The choices that produced this copy, sent again if the user keeps it. */
  request: TailorRequest | null;
  /** True while a skill is being moved to another row. */
  moving: boolean;
  onMove: (skill: string, row: string) => void;
  onClose: () => void;
}) {
  return (
    <Dialog open={tailored !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[94svh] flex-col gap-0 overflow-hidden rounded-3xl p-0 sm:max-w-3xl">
        {tailored && request ? (
          // Keyed by the file so a re-made copy starts from a clean state.
          <Body
            key={tailored.pdf.length + tailored.added.map((item) => item.row).join()}
            tailored={tailored}
            request={request}
            moving={moving}
            onMove={onMove}
            onClose={onClose}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function Body({
  tailored,
  request,
  moving,
  onMove,
  onClose,
}: {
  tailored: TailoredResume;
  request: TailorRequest;
  moving: boolean;
  onMove: (skill: string, row: string) => void;
  onClose: () => void;
}) {
  const keep = useKeepTailoredResume();
  // 'asking' shows the confirmation before the saved resume is replaced.
  const [saving, setSaving] = useState<'idle' | 'asking' | 'saved'>('idle');
  const [view, setView] = useState<View>('after');
  const [page, setPage] = useState(0);
  const pages = view === 'after' ? tailored.after : tailored.before;
  const count = tailored.added.length + tailored.changes.filter((change) => change.applied).length;

  function download() {
    const url = URL.createObjectURL(toPdfFile(tailored));
    const link = document.createElement('a');
    link.href = url;
    link.download = tailored.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  function saveAsMyResume() {
    keep.mutate(request, {
      onSuccess: () => {
        setSaving('saved');
        toast.success('Saved. Your job checks now use this resume.');
      },
      onError: (error) => {
        setSaving('idle');
        toast.error(errorMessage(error));
      },
    });
  }

  return (
    <>
      <DialogHeader className="border-b p-6 pb-4">
        <DialogTitle>
          {count} {count === 1 ? 'change' : 'changes'} made to your resume
        </DialogTitle>
        <DialogDescription>
          Only the words listed here changed; fonts, spacing and everything else are your original
          file. This is a preview: your saved resume, profile and scores change only if you press
          “Save as my resume”.
        </DialogDescription>
      </DialogHeader>

      <div className="flex-1 overflow-y-auto p-6 pt-4">
        <ul className="flex flex-col gap-2">
          {tailored.changes.map((change) => (
            <li key={`${change.kind}-${change.after}`} className="flex items-start gap-2 text-sm">
              {change.applied ? (
                <CircleCheck className="text-success mt-0.5 size-4 shrink-0" />
              ) : (
                <CircleAlert className="text-warning mt-0.5 size-4 shrink-0" />
              )}
              <span>
                <span className="text-muted-foreground">
                  {change.kind === 'headline' ? 'Headline: ' : 'Respelled: '}
                </span>
                {change.before ? <span className="line-through">{change.before}</span> : null}
                {change.before ? ' → ' : null}
                <span className="font-medium">{change.after}</span>
                {change.applied ? null : (
                  <span className="text-muted-foreground"> was not changed. {change.message}</span>
                )}
                {change.applied && !change.exact_font ? (
                  <span className="text-muted-foreground">
                    {' '}
                    (a look-alike font was used, check it in the preview)
                  </span>
                ) : null}
              </span>
            </li>
          ))}
          {tailored.added.map((item) => (
            <AddedRow
              key={item.skill}
              item={item}
              rows={tailored.rows}
              disabled={moving}
              onMove={(row) => onMove(item.skill, row)}
            />
          ))}
          {tailored.skipped.map((item) => (
            <li key={item.skill} className="flex items-start gap-2 text-sm">
              <CircleAlert className="text-warning mt-0.5 size-4 shrink-0" />
              <span>
                <span className="font-medium">{item.skill}</span>
                <span className="text-muted-foreground"> was not added. {item.message}</span>
              </span>
            </li>
          ))}
        </ul>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
          <div
            role="tablist"
            aria-label="Which version to show"
            className="bg-secondary inline-flex rounded-full p-1"
          >
            {(['after', 'before'] as const).map((option) => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={view === option}
                onClick={() => setView(option)}
                className={cn(
                  'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                  view === option
                    ? 'bg-background shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {option === 'after' ? 'Updated' : 'Original'}
              </button>
            ))}
          </div>
          {pages.length > 1 ? (
            <div className="flex items-center gap-2 text-sm">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <span className="text-muted-foreground">
                Page {page + 1} of {pages.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page === pages.length - 1}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          ) : null}
        </div>

        <div className="bg-secondary relative mt-3 overflow-hidden rounded-2xl border">
          {moving ? (
            <div className="bg-background/70 absolute inset-0 z-10 grid place-items-center">
              <Loader2 className="size-6 animate-spin motion-reduce:animate-none" />
            </div>
          ) : null}
          <PageImage
            // Remounted per image so the loading state shows for each one.
            key={`${view}-${page}`}
            src={`data:image/png;base64,${pages[page] ?? ''}`}
            alt={`${view === 'after' ? 'Updated' : 'Original'} resume, page ${page + 1}`}
          />
        </div>
      </div>

      {saving === 'asking' ? (
        <DialogFooter className="border-t p-4 sm:items-center sm:px-6">
          <p className="text-muted-foreground mr-auto text-sm">
            This replaces the resume saved in Rolesetu and adds the new skills to your profile, so
            every job check counts them from now on.
          </p>
          <Button variant="outline" disabled={keep.isPending} onClick={() => setSaving('idle')}>
            Cancel
          </Button>
          <Button disabled={keep.isPending} onClick={saveAsMyResume}>
            {keep.isPending ? (
              <Loader2 className="animate-spin motion-reduce:animate-none" />
            ) : null}
            {keep.isPending ? 'Saving…' : 'Replace my resume'}
          </Button>
        </DialogFooter>
      ) : (
        <DialogFooter className="border-t p-4 sm:px-6">
          <Button variant="ghost" className="sm:mr-auto" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="outline"
            disabled={moving || saving === 'saved'}
            onClick={() => setSaving('asking')}
          >
            {saving === 'saved' ? <CircleCheck /> : <Save />}
            {saving === 'saved' ? 'Saved as my resume' : 'Save as my resume'}
          </Button>
          <Button onClick={download} disabled={moving}>
            <Download />
            Download PDF
          </Button>
        </DialogFooter>
      )}
    </>
  );
}

function AddedRow({
  item,
  rows,
  disabled,
  onMove,
}: {
  item: AddedSkill;
  rows: string[];
  disabled: boolean;
  onMove: (row: string) => void;
}) {
  const id = `row-of-${item.skill}`;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <CircleCheck className="text-success size-4 shrink-0" />
      <span className="font-medium">{item.skill}</span>
      {rows.length > 1 && item.row ? (
        <>
          <label htmlFor={id} className="text-muted-foreground">
            in
          </label>
          <select
            id={id}
            value={item.row}
            disabled={disabled}
            onChange={(event) => onMove(event.target.value)}
            className="border-input bg-background h-8 rounded-full border px-3 text-sm"
          >
            {rows.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </>
      ) : null}
      {!item.exact_font ? (
        <span className="text-muted-foreground basis-full pl-7 text-xs">
          Your resume&apos;s font file does not include every letter of this word, so a matching
          look-alike font was used for it. Check it in the preview.
        </span>
      ) : null}
      {!item.readable ? (
        <span className="text-destructive basis-full pl-7 text-xs">
          We could not read this skill back from the new file, so a job site may miss it.
        </span>
      ) : null}
    </li>
  );
}

function PageImage({ src, alt }: { src: string; alt: string }) {
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  return (
    <>
      {state === 'loading' ? <Skeleton className="aspect-[1/1.414] w-full rounded-none" /> : null}
      {state === 'failed' ? (
        <p className="text-muted-foreground p-8 text-center text-sm">
          The preview could not be shown. You can still download the PDF.
        </p>
      ) : (
        // The image is embedded in the response, so there is nothing for the image optimiser to fetch.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          className={cn('w-full', state === 'loading' && 'hidden')}
          onLoad={() => setState('ready')}
          onError={() => setState('failed')}
        />
      )}
    </>
  );
}
