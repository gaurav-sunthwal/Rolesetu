'use client';

import { useMutation } from '@tanstack/react-query';
import {
  ArrowUp,
  Link2,
  CircleAlert,
  Loader2,
  Minus,
  Pencil,
  Plus,
  Sparkles,
  Undo2,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { type AssistEdit, askAssistant, type ResumeLayout } from '@/features/resume-editor/api';
import {
  type AssistUndo,
  changedLinks,
  type Draft,
  toAssistLines,
} from '@/features/resume-editor/draft';
import { errorMessage } from '@/lib/api/client';
import { newId } from '@/lib/format';
import { cn } from '@/lib/utils';

type Message =
  | { id: string; role: 'user'; text: string }
  | {
      id: string;
      role: 'assistant';
      text: string;
      applied: AssistEdit[];
      // Edits that mention something the user never gave: shown, not made.
      held: AssistEdit[];
      undo: AssistUndo | null;
      undone: boolean;
    }
  | { id: string; role: 'error'; text: string; retry: string };

const SUGGESTIONS = [
  'Add my latest project from my profile',
  'Add Docker and Kubernetes to my skills',
  'Make my bullets shorter and stronger',
  'Remove my school education',
];
const HISTORY_TURNS = 12;

export function ResumeAssistant({
  layout,
  draft,
  onApply,
  onUndo,
  onClose,
}: {
  layout: ResumeLayout;
  draft: Draft;
  /** Makes the edits in the editor and returns how to take them back. */
  onApply: (edits: AssistEdit[]) => AssistUndo;
  onUndo: (undo: AssistUndo) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const bottom = useRef<HTMLDivElement>(null);
  const ask = useMutation({ mutationFn: askAssistant });

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [messages, ask.isPending]);

  function send(text: string) {
    const message = text.trim();
    if (!message || ask.isPending) return;
    setInput('');
    const history = messages
      .filter((item) => item.role !== 'error')
      .slice(-HISTORY_TURNS)
      .map((item) => ({ role: item.role as 'user' | 'assistant', text: item.text }));
    setMessages((previous) => [
      ...previous.filter((item) => item.role !== 'error'),
      { id: newId(), role: 'user', text: message },
    ]);
    ask.mutate(
      {
        resume_id: layout.resume_id,
        message,
        history,
        lines: toAssistLines(draft),
        skills: draft.skills,
        links: changedLinks(layout, draft),
      },
      {
        onSuccess: (reply) => {
          const applied = reply.edits.filter((edit) => edit.unsupported.length === 0);
          const held = reply.edits.filter((edit) => edit.unsupported.length > 0);
          const undo = applied.length > 0 ? onApply(applied) : null;
          setMessages((previous) => [
            ...previous,
            {
              id: newId(),
              role: 'assistant',
              text: reply.reply,
              applied,
              held,
              undo,
              undone: false,
            },
          ]);
        },
        onError: (error) =>
          setMessages((previous) => [
            ...previous,
            { id: newId(), role: 'error', text: errorMessage(error), retry: message },
          ]),
      },
    );
  }

  function undo(id: string) {
    const message = messages.find((item) => item.id === id);
    if (message?.role !== 'assistant' || !message.undo) return;
    onUndo(message.undo);
    setMessages((previous) =>
      previous.map((item) => (item.id === id ? { ...item, undone: true } : item)),
    );
  }

  function addAnyway(id: string, edit: AssistEdit) {
    onApply([edit]);
    setMessages((previous) =>
      previous.map((item) =>
        item.id === id && item.role === 'assistant'
          ? { ...item, held: item.held.filter((other) => other !== edit) }
          : item,
      ),
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start gap-3 border-b px-4 py-3">
        <span className="bg-primary/10 text-primary flex size-8 shrink-0 items-center justify-center rounded-full">
          <Sparkles className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Resume assistant</p>
          <p className="text-muted-foreground text-xs">
            Edits your resume from your words and profile. Nothing is saved until you press Save.
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="Close assistant" onClick={onClose}>
          <X />
        </Button>
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-col gap-2">
            <p className="text-muted-foreground text-sm">Try one of these, or type your own:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => send(suggestion)}
                  className="bg-secondary hover:bg-secondary/70 focus-visible:ring-ring/50 rounded-full px-3 py-1.5 text-left text-xs font-medium outline-none focus-visible:ring-3"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((message) =>
          message.role === 'user' ? (
            <p
              key={message.id}
              className="bg-primary text-primary-foreground max-w-[85%] self-end rounded-2xl rounded-br-md px-3.5 py-2 text-sm"
            >
              {message.text}
            </p>
          ) : message.role === 'error' ? (
            <div
              key={message.id}
              role="alert"
              className="bg-destructive/5 text-destructive flex max-w-[90%] flex-col gap-2 rounded-2xl rounded-bl-md px-3.5 py-2 text-sm"
            >
              <span className="flex items-start gap-2">
                <CircleAlert className="mt-0.5 size-4 shrink-0" />
                <span>
                  {message.text}
                  {/503|unavailable|key/i.test(message.text) ? (
                    <>
                      {' '}
                      <Link href="/app/settings" className="underline underline-offset-2">
                        Open Settings
                      </Link>
                    </>
                  ) : null}
                </span>
              </span>
              <Button
                size="sm"
                variant="outline"
                className="self-start"
                onClick={() => send(message.retry)}
              >
                Try again
              </Button>
            </div>
          ) : (
            <AssistantMessage
              key={message.id}
              text={message.text}
              applied={message.applied}
              held={message.held}
              undone={message.undone}
              canUndo={!!message.undo && !message.undone}
              onUndo={() => undo(message.id)}
              onAddAnyway={(edit) => addAnyway(message.id, edit)}
            />
          ),
        )}

        {ask.isPending ? (
          <p
            className="text-muted-foreground flex items-center gap-2 self-start text-sm"
            aria-live="polite"
          >
            <Loader2 className="size-4 animate-spin motion-reduce:animate-none" />
            Working on your resume…
          </p>
        ) : null}
        <div ref={bottom} />
      </div>

      <form
        className="flex items-end gap-2 border-t p-3"
        onSubmit={(event) => {
          event.preventDefault();
          send(input);
        }}
      >
        <textarea
          aria-label="Message the resume assistant"
          rows={1}
          maxLength={1000}
          value={input}
          placeholder="e.g. Add my Rolesetu project"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              send(input);
            }
          }}
          className="border-input focus-visible:border-ring focus-visible:ring-ring/50 field-sizing-content max-h-32 min-h-10 flex-1 resize-none rounded-2xl border bg-transparent px-3.5 py-2 text-sm outline-none focus-visible:ring-3"
        />
        <Button
          type="submit"
          size="icon"
          aria-label="Send"
          disabled={!input.trim() || ask.isPending}
        >
          <ArrowUp />
        </Button>
      </form>
    </div>
  );
}

const KIND = {
  change: { icon: Pencil, label: 'Changed' },
  remove: { icon: Minus, label: 'Removed' },
  add_below: { icon: Plus, label: 'Added' },
  add_skill: { icon: Plus, label: 'Skill' },
  set_link: { icon: Link2, label: 'Link' },
} as const;

function EditRow({ edit }: { edit: AssistEdit }) {
  const { icon: Icon, label } = KIND[edit.kind];
  return (
    <span className="flex items-start gap-2">
      <Icon className="text-muted-foreground mt-0.5 size-3.5 shrink-0" />
      <span className="min-w-0">
        <span className="text-muted-foreground">
          {label}
          {edit.section ? ` in ${edit.section}` : ''}:{' '}
        </span>
        {edit.kind === 'remove' ? (
          <span className="line-through">{edit.before}</span>
        ) : (
          <span className="font-medium">{edit.text}</span>
        )}
      </span>
    </span>
  );
}

function AssistantMessage({
  text,
  applied,
  held,
  undone,
  canUndo,
  onUndo,
  onAddAnyway,
}: {
  text: string;
  applied: AssistEdit[];
  held: AssistEdit[];
  undone: boolean;
  canUndo: boolean;
  onUndo: () => void;
  onAddAnyway: (edit: AssistEdit) => void;
}) {
  return (
    <div className="bg-secondary flex max-w-[92%] flex-col gap-2 self-start rounded-2xl rounded-bl-md px-3.5 py-2.5 text-sm">
      <p>{text}</p>
      {applied.length > 0 ? (
        <ul className={cn('flex flex-col gap-1 text-xs', undone && 'opacity-50')}>
          {applied.map((edit, index) => (
            <li key={index}>
              <EditRow edit={edit} />
            </li>
          ))}
        </ul>
      ) : null}
      {held.length > 0 ? (
        <ul className="flex flex-col gap-2 text-xs">
          {held.map((edit, index) => (
            <li key={index} className="bg-background flex flex-col gap-1.5 rounded-xl p-2">
              <EditRow edit={edit} />
              <span className="text-muted-foreground flex items-start gap-1.5">
                <CircleAlert className="text-warning mt-px size-3.5 shrink-0" />
                Not added yet: it mentions {edit.unsupported.join(', ')}, which is not in your
                resume, profile or messages. Add it only if it is true.
              </span>
              <Button
                size="xs"
                variant="outline"
                className="self-start"
                onClick={() => onAddAnyway(edit)}
              >
                It is true, add it
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {applied.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {undone ? (
            <span className="text-muted-foreground text-xs">Undone.</span>
          ) : (
            <>
              <Button size="xs" variant="outline" disabled={!canUndo} onClick={onUndo}>
                <Undo2 />
                Undo
              </Button>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

/**
 * A round button in the corner that opens the assistant in a floating window.
 * The window stays mounted when closed, so the conversation is kept.
 */
export function AssistantLauncher(props: Omit<Parameters<typeof ResumeAssistant>[0], 'onClose'>) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);

  return (
    <>
      <div
        role="dialog"
        aria-label="Resume assistant"
        aria-hidden={!open}
        inert={!open}
        className={cn(
          'bg-popover text-popover-foreground fixed z-40 flex flex-col overflow-hidden rounded-3xl border shadow-2xl',
          'inset-x-3 top-20 bottom-24 sm:inset-x-auto sm:top-auto sm:right-6 sm:bottom-24 sm:h-[min(600px,calc(100svh-9rem))] sm:w-[400px]',
          'origin-bottom-right motion-safe:transition-[opacity,transform] motion-safe:duration-200',
          open ? 'opacity-100' : 'pointer-events-none translate-y-2 scale-95 opacity-0',
        )}
      >
        <ResumeAssistant {...props} onClose={() => setOpen(false)} />
      </div>
      <button
        ref={button}
        type="button"
        aria-label={open ? 'Close resume assistant' : 'Ask AI to edit your resume'}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className={cn(
          'focus-visible:ring-ring/50 fixed right-4 bottom-4 z-40 flex h-14 items-center gap-2 rounded-full px-5 font-medium shadow-lg outline-none focus-visible:ring-4 sm:right-6 sm:bottom-6',
          'motion-safe:transition-colors',
          open
            ? 'bg-foreground text-background'
            : 'bg-primary text-primary-foreground hover:bg-primary/90',
        )}
      >
        {open ? <X className="size-5" /> : <Sparkles className="size-5" />}
        <span className={cn('text-sm', open && 'sr-only')}>Ask AI</span>
      </button>
    </>
  );
}
