'use client';

import { CircleAlert, Link2, Plus, RotateCcw, Trash2, Undo2, X } from 'lucide-react';
import { type KeyboardEvent, type ReactNode, useState } from 'react';

import type { EditorLine, EditorLink } from '@/features/resume-editor/api';
import type { LineDraft } from '@/features/resume-editor/draft';
import { ADDRESS, isChanged } from '@/features/resume-editor/draft';
import { cn } from '@/lib/utils';

const ACTION =
  'text-muted-foreground hover:bg-background hover:text-foreground focus-visible:ring-ring/50 flex size-7 shrink-0 items-center justify-center rounded-full outline-none focus-visible:ring-3 disabled:pointer-events-none disabled:opacity-40';
// Always visible on touch screens; on wider screens only on hover or focus.
const ACTIONS =
  'flex items-center gap-0.5 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100';
const TEXT =
  'field-sizing-content min-h-6 w-full min-w-0 resize-none bg-transparent text-sm leading-6 outline-none placeholder:text-muted-foreground/70';

export function lineInputId(id: string): string {
  return `resume-line-${id}`;
}

export function focusInput(id: string): void {
  // After React has drawn the new field.
  window.requestAnimationFrame(() => {
    const input = document.getElementById(id);
    if (input instanceof HTMLTextAreaElement) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
      input.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  });
}

function Problem({ children }: { children: ReactNode }) {
  return (
    <p className="text-muted-foreground flex items-start gap-1.5 pt-1 pl-1 text-xs" role="status">
      <CircleAlert className="text-warning mt-px size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function Bullet({ show }: { show: boolean }) {
  return show ? (
    <span aria-hidden className="text-muted-foreground w-3 shrink-0 text-sm leading-6">
      •
    </span>
  ) : null;
}

/** Lines are single lines on the page: Enter makes a new one instead of a line break. */
function onEnter(handler: () => void) {
  return (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
      event.preventDefault();
      handler();
    }
  };
}

export function LineField({
  line,
  draft,
  problem,
  onFocus,
  onChange,
  onRemove,
  onRestore,
  onReset,
  onAddBelow,
}: {
  line: EditorLine;
  draft: LineDraft | undefined;
  problem: string | undefined;
  onFocus: () => void;
  onChange: (text: string) => void;
  onRemove: () => void;
  onRestore: () => void;
  onReset: () => void;
  onAddBelow: () => void;
}) {
  const removed = !!draft?.removed;
  const changed = isChanged(line, draft);
  const value = draft?.text ?? line.text;
  const label = line.heading ? `Heading: ${line.text}` : `Resume line: ${line.text}`;

  return (
    <div className="min-w-0">
      <div
        className={cn(
          'group hover:bg-secondary/70 focus-within:bg-secondary flex items-start gap-2 rounded-xl py-1 pr-1 pl-2 transition-colors',
          changed && 'bg-primary/5 ring-primary/25 ring-1',
          removed && 'bg-destructive/5',
        )}
      >
        <Bullet show={line.bullet} />
        <textarea
          id={lineInputId(line.id)}
          aria-label={label}
          rows={1}
          spellCheck
          readOnly={removed}
          value={value}
          onFocus={onFocus}
          onChange={(event) => onChange(event.target.value.replace(/\s*\n\s*/g, ' '))}
          onKeyDown={line.can_add_below && !removed ? onEnter(onAddBelow) : undefined}
          className={cn(
            TEXT,
            line.bold && 'font-semibold',
            line.italic && 'italic',
            line.heading && 'font-semibold tracking-tight',
            line.right_aligned && 'text-muted-foreground text-[0.8rem]',
            removed && 'text-muted-foreground line-through',
          )}
        />
        <div className={ACTIONS}>
          {removed ? (
            <button type="button" className={ACTION} onClick={onRestore} aria-label="Restore line">
              <Undo2 className="size-4" />
            </button>
          ) : (
            <>
              {changed ? (
                <button
                  type="button"
                  className={ACTION}
                  onClick={onReset}
                  aria-label="Undo changes to this line"
                  title="Undo changes to this line"
                >
                  <RotateCcw className="size-3.5" />
                </button>
              ) : null}
              <button
                type="button"
                className={ACTION}
                onClick={onAddBelow}
                disabled={!line.can_add_below}
                aria-label="Add a line below"
                title={
                  line.can_add_below
                    ? 'Add a line below (or press Enter)'
                    : 'Lines cannot be added on a page laid out in columns yet'
                }
              >
                <Plus className="size-4" />
              </button>
              <button
                type="button"
                className={cn(ACTION, 'hover:text-destructive')}
                onClick={onRemove}
                aria-label="Remove line"
                title="Remove line"
              >
                <Trash2 className="size-3.5" />
              </button>
            </>
          )}
        </div>
      </div>
      {problem ? <Problem>{problem}</Problem> : null}
    </div>
  );
}

export function NewLineField({
  id,
  text,
  look,
  problem,
  onFocus,
  onChange,
  onAddAnother,
  onRemove,
}: {
  id: string;
  text: string;
  /** The line whose look the new line copies on the page. */
  look: Pick<EditorLine, 'bullet' | 'bold' | 'italic'>;
  problem: string | undefined;
  onFocus: () => void;
  onChange: (text: string) => void;
  onAddAnother: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="min-w-0">
      <div className="group bg-success/5 ring-success/30 focus-within:bg-success/10 flex items-start gap-2 rounded-xl py-1 pr-1 pl-2 ring-1">
        <Bullet show={look.bullet} />
        <textarea
          id={id}
          aria-label="New line"
          rows={1}
          spellCheck
          placeholder="Type the new line…"
          value={text}
          onFocus={onFocus}
          onChange={(event) => onChange(event.target.value.replace(/\s*\n\s*/g, ' '))}
          onKeyDown={(event) => {
            if (event.key === 'Backspace' && text === '') {
              event.preventDefault();
              onRemove();
              return;
            }
            onEnter(onAddAnother)(event);
          }}
          className={cn(TEXT, look.bold && 'font-semibold', look.italic && 'italic')}
        />
        <span className="bg-success/15 text-success mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[0.7rem] font-semibold">
          New
        </span>
        <button
          type="button"
          className={ACTION}
          onClick={onRemove}
          aria-label="Remove this new line"
        >
          <X className="size-4" />
        </button>
      </div>
      {problem ? <Problem>{problem}</Problem> : null}
    </div>
  );
}

/** A link on a line: the words it is drawn over and where they go, editable in place. */
export function LinkField({
  link,
  value,
  onChange,
}: {
  link: EditorLink;
  value: string | undefined;
  onChange: (uri: string | undefined) => void;
}) {
  const [editing, setEditing] = useState(false);
  const uri = value ?? link.uri;
  const changed = value !== undefined && value.trim() !== link.uri;
  const valid = ADDRESS.test(uri.trim());

  return (
    <div className="flex min-w-0 items-center gap-1.5 pl-5 text-xs">
      <Link2
        className={cn('size-3.5 shrink-0', changed ? 'text-primary' : 'text-muted-foreground')}
      />
      {editing ? (
        <input
          autoFocus
          aria-label={`Address for ${link.text}`}
          aria-invalid={!valid}
          value={uri}
          onChange={(event) => onChange(event.target.value)}
          onBlur={() => setEditing(false)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === 'Escape') setEditing(false);
          }}
          className={cn(
            'border-input focus-visible:border-ring h-7 min-w-0 flex-1 rounded-md border bg-transparent px-2 outline-none',
            !valid && 'border-destructive',
          )}
        />
      ) : (
        <button
          type="button"
          onClick={() => setEditing(true)}
          title="Change where this link goes"
          className={cn(
            'hover:bg-secondary focus-visible:ring-ring/50 min-w-0 truncate rounded-md px-1.5 py-0.5 text-left outline-none focus-visible:ring-2',
            changed ? 'text-primary font-medium' : 'text-muted-foreground',
          )}
        >
          {uri.replace(/^https?:\/\//, '').replace(/\/$/, '')}
        </button>
      )}
      {!valid && editing ? (
        <span className="text-destructive shrink-0">Starts with https://</span>
      ) : null}
      {changed && !editing ? (
        <button
          type="button"
          aria-label="Undo link change"
          title="Undo link change"
          onClick={() => onChange(undefined)}
          className="text-muted-foreground hover:text-foreground shrink-0"
        >
          <RotateCcw className="size-3" />
        </button>
      ) : null}
    </div>
  );
}
