'use client';

import { ChevronLeft, ChevronRight, CircleAlert, CircleCheck, Loader2 } from 'lucide-react';
import { type MouseEvent, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { EditorLine, ResumeLayout } from '@/features/resume-editor/api';
import { cn } from '@/lib/utils';

export type PreviewStatus = 'unchanged' | 'updating' | 'ready' | 'failed';
type View = 'edited' | 'original';

export function ResumePreview({
  layout,
  editedPages,
  status,
  error,
  lookAlikeFont,
  focusedLine,
  movedPages,
  onRetry,
  onPickLine,
}: {
  layout: ResumeLayout;
  /** The latest drawing of the edited resume, if there is one yet. */
  editedPages: string[] | null;
  status: PreviewStatus;
  error: string | null;
  /** A look-alike font had to be used for some letters. */
  lookAlikeFont: boolean;
  focusedLine: EditorLine | null;
  /** Pages where lines moved, so the original outlines no longer line up. */
  movedPages: Set<number>;
  onRetry: () => void;
  onPickLine: (line: EditorLine) => void;
}) {
  const [view, setView] = useState<View>('edited');
  const [chosenPage, setChosenPage] = useState(0);
  const showEdited = view === 'edited' && editedPages !== null;
  const pages = showEdited ? editedPages : layout.pages.map((page) => page.image);
  const count = pages.length;
  // Follow the line being edited onto its page; otherwise the page the user chose.
  const page = Math.min(focusedLine?.page ?? chosenPage, Math.max(0, count - 1));
  const size = layout.pages[page] ?? layout.pages[0];
  // Outlines are where lines sit in the original file. Once lines move on a
  // page, they would point at the wrong place in the edited drawing.
  const outlinesFit = !showEdited || !movedPages.has(page);

  function linesOnPage(): EditorLine[] {
    return layout.sections.flatMap((section) => section.lines).filter((line) => line.page === page);
  }

  function pick(event: MouseEvent<HTMLDivElement>) {
    if (!outlinesFit || !size) return;
    const area = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - area.left) / area.width) * size.width;
    const y = ((event.clientY - area.top) / area.height) * size.height;
    const hit = linesOnPage().find(
      ({ box }) => x >= box[0] - 2 && x <= box[2] + 2 && y >= box[1] - 2 && y <= box[3] + 2,
    );
    if (hit) onPickLine(hit);
  }

  const highlight =
    focusedLine && focusedLine.page === page && outlinesFit && size ? focusedLine.box : null;

  return (
    <section
      id="resume-preview"
      aria-label="Resume preview"
      className="bg-secondary/60 flex min-w-0 flex-col gap-4 rounded-3xl p-3 sm:p-6"
    >
      <div className="mx-auto flex w-full max-w-[820px] flex-wrap items-center justify-between gap-2">
        <div
          role="tablist"
          aria-label="Which version to show"
          className="bg-background/80 inline-flex rounded-full p-1 shadow-xs"
        >
          {(['edited', 'original'] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={view === option}
              onClick={() => setView(option)}
              className={cn(
                'rounded-full px-3.5 py-1 text-xs font-medium transition-colors',
                view === option
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {option === 'edited' ? 'Edited' : 'Original'}
            </button>
          ))}
        </div>
        {count > 1 ? (
          <div className="flex items-center gap-1 text-xs">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Previous page"
              disabled={page === 0}
              onClick={() => setChosenPage(page - 1)}
            >
              <ChevronLeft />
            </Button>
            <span className="text-muted-foreground tabular-nums">
              {page + 1} / {count}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Next page"
              disabled={page === count - 1}
              onClick={() => setChosenPage(page + 1)}
            >
              <ChevronRight />
            </Button>
          </div>
        ) : null}
      </div>

      {error && view === 'edited' ? (
        <div
          role="alert"
          className="bg-background text-destructive mx-auto flex w-full max-w-[820px] flex-wrap items-center gap-2 rounded-2xl px-3 py-2 text-sm"
        >
          <CircleAlert className="size-4 shrink-0" />
          <span className="min-w-0 flex-1">{error}</span>
          <Button size="sm" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : null}
      {lookAlikeFont && view === 'edited' ? (
        <p className="text-muted-foreground mx-auto flex w-full max-w-[820px] items-center gap-1.5 text-xs">
          <span aria-hidden className="bg-warning size-1.5 shrink-0 rounded-full" />A look-alike
          font was used for letters your resume&apos;s font lacks. Check the changed words.
        </p>
      ) : null}

      <div
        className={cn(
          'relative mx-auto w-full max-w-[820px] overflow-hidden rounded-sm bg-white shadow-xl ring-1 ring-black/5',
          outlinesFit && 'cursor-text',
        )}
        onClick={pick}
      >
        {status === 'updating' && view === 'edited' ? (
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden">
            <div className="bg-primary h-full w-1/3 motion-safe:animate-[resume-progress_1.1s_ease-in-out_infinite]" />
          </div>
        ) : null}
        <PageImage
          key={`${view}-${page}`}
          src={`data:image/png;base64,${pages[page] ?? ''}`}
          alt={`${showEdited ? 'Edited' : 'Original'} resume, page ${page + 1}`}
        />
        {highlight && size ? (
          <div
            aria-hidden
            className="ring-primary bg-primary/10 pointer-events-none absolute rounded-sm ring-2 motion-safe:transition-all"
            style={{
              left: `${((highlight[0] - 2) / size.width) * 100}%`,
              top: `${((highlight[1] - 1) / size.height) * 100}%`,
              width: `${((highlight[2] - highlight[0] + 4) / size.width) * 100}%`,
              height: `${((highlight[3] - highlight[1] + 2) / size.height) * 100}%`,
            }}
          />
        ) : null}
      </div>
      <p className="text-muted-foreground text-center text-xs">
        Your own PDF, redrawn as you edit. Click any line on the page to edit it.
      </p>
    </section>
  );
}

export function StatusPill({ status }: { status: PreviewStatus }) {
  if (status === 'updating') {
    return (
      <span className="text-muted-foreground flex items-center gap-1.5 text-xs" aria-live="polite">
        <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" />
        <span className="hidden sm:inline">Updating preview…</span>
      </span>
    );
  }
  if (status === 'ready') {
    return (
      <span className="text-muted-foreground flex items-center gap-1.5 text-xs" aria-live="polite">
        <CircleCheck className="text-success size-3.5" />
        <span className="hidden sm:inline">Preview up to date</span>
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="text-destructive flex items-center gap-1.5 text-xs" aria-live="polite">
        <CircleAlert className="size-3.5" />
        Preview failed
      </span>
    );
  }
  return <span className="text-muted-foreground hidden text-xs sm:inline">No changes yet</span>;
}

/** Keeps showing the last page drawn until the next one is ready, so updates never flash. */
function PageImage({ src, alt }: { src: string; alt: string }) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  if (failed === src) {
    return (
      <p className="text-muted-foreground p-8 text-center text-sm">
        The preview could not be shown. You can still download the PDF.
      </p>
    );
  }
  return (
    <>
      {loaded ? null : <Skeleton className="aspect-[1/1.414] w-full rounded-none" />}
      {/* The image is embedded in the response, so there is nothing for the image optimiser to fetch. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        draggable={false}
        className={cn('w-full select-none', !loaded && 'hidden')}
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(src)}
      />
    </>
  );
}
