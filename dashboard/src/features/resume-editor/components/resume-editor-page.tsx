'use client';

import {
  CircleAlert,
  CircleCheck,
  Download,
  FileText,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Save,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/app/confirm-dialog';
import { inputClass } from '@/components/app/field';
import { EmptyState, ErrorState, InlineError } from '@/components/app/states';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useApplyResume } from '@/features/resume/hooks';
import {
  type EditedResume,
  type EditorLine,
  type EditorSection,
  type ResumeLayout,
  toPdfFile,
} from '@/features/resume-editor/api';
import {
  addLineBelow,
  applyAssistEdits,
  type AssistUndo,
  countChanges,
  type Draft,
  EMPTY_DRAFT,
  isChanged,
  movedPages,
  problemsByTarget,
  readDraft,
  toRequest,
  undoAssistEdits,
  updateLine,
  writeDraft,
} from '@/features/resume-editor/draft';
import { AssistantLauncher } from '@/features/resume-editor/components/resume-assistant';
import type { AssistEdit } from '@/features/resume-editor/api';
import {
  focusInput,
  LineField,
  lineInputId,
  LinkField,
  NewLineField,
} from '@/features/resume-editor/components/line-field';
import {
  type PreviewStatus,
  ResumePreview,
  StatusPill,
} from '@/features/resume-editor/components/resume-preview';
import {
  useLivePreview,
  useResumeLayout,
  useSaveResumeEdits,
} from '@/features/resume-editor/hooks';
import { ApiError, errorMessage } from '@/lib/api/client';
import { newId } from '@/lib/format';
import { cn } from '@/lib/utils';

const MAX_SKILLS = 12;

const EDITOR_OPEN_KEY = 'rolesetu:resume-editor:lines-open';

/** The line editor starts open on wide screens, closed on phones, then as the user left it. */
function readEditorOpen(): boolean {
  try {
    const saved = window.localStorage.getItem(EDITOR_OPEN_KEY);
    if (saved !== null) return saved === '1';
  } catch {
    // Storage blocked: fall back to the screen size.
  }
  return window.matchMedia('(min-width: 1024px)').matches;
}

function newInputId(key: string): string {
  return `resume-new-line-${key}`;
}

export function ResumeEditorPage() {
  const layout = useResumeLayout();

  if (layout.isPending) {
    return (
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
        <Skeleton className="h-9 w-72 rounded-full" />
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(340px,420px)_minmax(0,1fr)]">
          <Skeleton className="hidden h-[70svh] rounded-3xl lg:block" />
          <Skeleton className="mx-auto aspect-[1/1.414] w-full max-w-[820px] rounded-3xl" />
        </div>
      </div>
    );
  }
  if (layout.isError) {
    const noResume = layout.error instanceof ApiError && layout.error.status === 404;
    return (
      <div className="mx-auto w-full max-w-6xl">
        <section className="bg-card rounded-3xl border p-5 sm:p-6">
          {noResume ? (
            <EmptyState
              icon={FileText}
              title="No resume to edit yet"
              body="Upload your resume on the Profile page. You can then change any line of it here, and it keeps its own fonts and layout."
              action={
                <Button nativeButton={false} render={<Link href="/app/profile" />}>
                  Upload your resume
                </Button>
              }
            />
          ) : (
            <ErrorState error={layout.error} onRetry={() => layout.refetch()} />
          )}
        </section>
      </div>
    );
  }
  // Keyed by the file, so saving (which makes a new file) starts a clean editor.
  return <Editor key={layout.data.resume_id} layout={layout.data} />;
}

/** Lines that sit side by side on the page (a company and its dates) share a row. */
function rowsOf(section: EditorSection): EditorLine[][] {
  const rows: EditorLine[][] = [];
  for (const line of section.lines) {
    const row = rows.at(-1);
    const first = row?.[0];
    if (row && first && first.page === line.page && Math.abs(first.box[3] - line.box[3]) < 3) {
      row.push(line);
    } else {
      rows.push([line]);
    }
  }
  return rows;
}

function Editor({ layout }: { layout: ResumeLayout }) {
  const [draft, setDraft] = useState<Draft>(() => readDraft(layout.resume_id));
  const [focused, setFocused] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(readEditorOpen);
  // The assistant's reply arrives after a wait; its edits go onto the draft as it is then.
  const latestDraft = useRef(draft);
  useEffect(() => {
    latestDraft.current = draft;
  }, [draft]);

  function toggleEditor(open: boolean) {
    setEditorOpen(open);
    try {
      window.localStorage.setItem(EDITOR_OPEN_KEY, open ? '1' : '0');
    } catch {
      // Storage blocked: the choice lasts until the page is left.
    }
  }

  function applyFromAssistant(edits: AssistEdit[]): AssistUndo {
    const result = applyAssistEdits(latestDraft.current, edits);
    latestDraft.current = result.draft;
    setDraft(result.draft);
    return result.undo;
  }

  function undoFromAssistant(undo: AssistUndo) {
    const next = undoAssistEdits(latestDraft.current, undo);
    latestDraft.current = next;
    setDraft(next);
  }
  const [confirming, setConfirming] = useState<'save' | 'discard' | null>(null);
  const save = useSaveResumeEdits();
  const apply = useApplyResume();

  const built = useMemo(() => toRequest(layout, draft), [layout, draft]);
  const preview = useLivePreview(built?.request ?? null);
  const changes = countChanges(layout, draft);
  const current = preview.isCurrent ? (preview.data ?? null) : null;
  const problems = current && built ? problemsByTarget(built.targets, current.outcomes) : {};
  const moved = useMemo(() => movedPages(layout, draft), [layout, draft]);
  const lines = useMemo(
    () =>
      new Map(layout.sections.flatMap((section) => section.lines).map((line) => [line.id, line])),
    [layout],
  );

  useEffect(() => writeDraft(layout.resume_id, draft), [layout.resume_id, draft]);

  // Leaving the page would lose unsaved edits only if storage is blocked,
  // but a reminder costs nothing.
  useEffect(() => {
    if (changes === 0) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [changes]);

  let status: PreviewStatus = 'unchanged';
  if (built) {
    if (preview.isUpdating) status = 'updating';
    else if (preview.isError) status = 'failed';
    else if (current) status = 'ready';
    else status = 'updating';
  }
  const lookAlike = !!current?.outcomes.some((outcome) => outcome.applied && !outcome.exact_font);

  function edit(lineId: string, change: Parameters<typeof updateLine>[2]) {
    setDraft((previous) => updateLine(previous, lineId, change));
  }

  function addBelow(lineId: string) {
    const { draft: next, key } = addLineBelow(draft, lineId);
    setDraft(next);
    focusInput(newInputId(key));
  }

  function addAfterNew(lineId: string, afterKey: string) {
    const key = newId();
    edit(lineId, (current) => {
      const added = [...(current.added ?? [])];
      added.splice(added.findIndex((item) => item.key === afterKey) + 1, 0, { key, text: '' });
      return { ...current, added };
    });
    focusInput(newInputId(key));
  }

  function removeNew(lineId: string, key: string) {
    const list = draft.lines[lineId]?.added ?? [];
    const index = list.findIndex((item) => item.key === key);
    const before = list[index - 1];
    edit(lineId, (current) => ({
      ...current,
      added: (current.added ?? []).filter((item) => item.key !== key),
    }));
    focusInput(before ? newInputId(before.key) : lineInputId(lineId));
  }

  function download(edited: EditedResume) {
    const url = URL.createObjectURL(toPdfFile(edited));
    const link = document.createElement('a');
    link.href = url;
    link.download = edited.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  function saveAsResume() {
    if (!built) return;
    save.mutate(built.request, {
      onSuccess: (saved) => {
        writeDraft(layout.resume_id, EMPTY_DRAFT);
        setConfirming(null);
        toast.success('Saved. Job checks and autofill now use your edited resume.', {
          description: 'Want your profile to match it too?',
          action: {
            label: 'Update profile',
            onClick: () =>
              apply.mutate(
                { id: saved.id, mode: 'merge' },
                {
                  onSuccess: () => toast.success('Profile updated from your edited resume.'),
                  onError: (error) => toast.error(errorMessage(error)),
                },
              ),
          },
        });
      },
      onError: (error) => {
        setConfirming(null);
        toast.error(errorMessage(error));
      },
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
      <div className="bg-background/85 sticky top-16 z-20 -mx-4 -mt-8 flex flex-wrap items-center gap-2 border-b border-dashed px-4 py-3 backdrop-blur-lg sm:-mx-6 sm:px-6">
        <Button
          variant={editorOpen ? 'secondary' : 'outline'}
          size="sm"
          aria-pressed={editorOpen}
          onClick={() => toggleEditor(!editorOpen)}
        >
          {editorOpen ? <PanelLeftClose /> : <PanelLeftOpen />}
          {editorOpen ? 'Hide lines' : 'Edit lines'}
        </Button>
        <StatusPill status={status} />
        {changes > 0 ? (
          <span className="bg-primary/10 text-primary rounded-full px-2.5 py-0.5 text-xs font-semibold">
            {changes} {changes === 1 ? 'change' : 'changes'}
          </span>
        ) : null}
        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            disabled={changes === 0 || save.isPending}
            onClick={() => setConfirming('discard')}
          >
            Discard
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!current || save.isPending}
            onClick={() => current && download(current)}
          >
            <Download />
            <span className="hidden sm:inline">Download</span>
          </Button>
          <Button
            size="sm"
            disabled={!built || save.isPending || status === 'failed'}
            onClick={() => setConfirming('save')}
          >
            {save.isPending ? (
              <Loader2 className="animate-spin motion-reduce:animate-none" />
            ) : (
              <Save />
            )}
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>

      <div
        className={cn(
          'grid items-start gap-6',
          editorOpen && 'lg:grid-cols-[minmax(340px,420px)_minmax(0,1fr)]',
        )}
      >
        {editorOpen ? (
          <aside
            aria-label="Edit lines"
            className="bg-card flex flex-col rounded-3xl border lg:sticky lg:top-36 lg:max-h-[calc(100svh-10.5rem)]"
          >
            <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold">Edit lines</p>
                <p className="text-muted-foreground text-xs">
                  Click a line to change it. Enter adds a line below.
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Close line editor"
                onClick={() => toggleEditor(false)}
              >
                <X />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-2">
              {layout.sections.map((section, index) => (
                <SectionEditor
                  key={`${index}-${section.title}`}
                  section={section}
                  draft={draft}
                  problems={problems}
                  onFocus={setFocused}
                  onEdit={edit}
                  onAddBelow={addBelow}
                  onAddAfterNew={addAfterNew}
                  onRemoveNew={removeNew}
                  lookOf={(lineId) => lines.get(lineId)}
                  onLink={(linkId, uri) =>
                    setDraft((previous) => {
                      const links = { ...previous.links };
                      if (uri === undefined) delete links[linkId];
                      else links[linkId] = uri;
                      return { ...previous, links };
                    })
                  }
                >
                  {section.is_skills ? (
                    <SkillAdder
                      skills={draft.skills}
                      rows={layout.skill_rows}
                      result={current}
                      onChange={(skills) => setDraft((previous) => ({ ...previous, skills }))}
                    />
                  ) : null}
                </SectionEditor>
              ))}
            </div>
          </aside>
        ) : null}

        <ResumePreview
          layout={layout}
          editedPages={preview.data?.pages ?? null}
          status={status}
          error={preview.isError && built ? errorMessage(preview.error) : null}
          lookAlikeFont={lookAlike}
          focusedLine={focused ? (lines.get(focused) ?? null) : null}
          movedPages={moved}
          onRetry={() => void preview.refetch()}
          onPickLine={(line) => {
            setFocused(line.id);
            toggleEditor(true);
            focusInput(lineInputId(line.id));
          }}
        />
      </div>

      <AssistantLauncher
        layout={layout}
        draft={draft}
        onApply={applyFromAssistant}
        onUndo={undoFromAssistant}
      />

      <ConfirmDialog
        open={confirming === 'save'}
        onOpenChange={(open) => !open && setConfirming(null)}
        title="Replace your saved resume?"
        description="Your edited resume becomes the one Rolesetu uses for job checks, tailoring and autofill. Skills you added go onto your profile. Download the original first if you want to keep a copy."
        confirmLabel="Replace my resume"
        pending={save.isPending}
        onConfirm={saveAsResume}
      />
      <ConfirmDialog
        open={confirming === 'discard'}
        onOpenChange={(open) => !open && setConfirming(null)}
        title="Discard your changes?"
        description={`All ${changes} ${changes === 1 ? 'change' : 'changes'} will be undone. Your saved resume is not affected.`}
        confirmLabel="Discard changes"
        onConfirm={() => {
          setDraft(EMPTY_DRAFT);
          setFocused(null);
          setConfirming(null);
        }}
      />
    </div>
  );
}

function SectionEditor({
  section,
  draft,
  problems,
  onFocus,
  onEdit,
  onAddBelow,
  onAddAfterNew,
  onRemoveNew,
  lookOf,
  onLink,
  children,
}: {
  section: EditorSection;
  draft: Draft;
  problems: Record<string, string>;
  onFocus: (lineId: string) => void;
  onEdit: (lineId: string, change: Parameters<typeof updateLine>[2]) => void;
  onAddBelow: (lineId: string) => void;
  onAddAfterNew: (lineId: string, afterKey: string) => void;
  onRemoveNew: (lineId: string, key: string) => void;
  /** The line a new line copies the look of. */
  lookOf: (lineId: string) => EditorLine | undefined;
  onLink: (linkId: string, uri: string | undefined) => void;
  children?: ReactNode;
}) {
  const edited = section.lines.filter((line) => {
    const change = draft.lines[line.id];
    return change?.removed || isChanged(line, change) || change?.added?.some((a) => a.text.trim());
  }).length;
  const title = section.title === 'Header' ? 'Name and contact' : section.title;
  // The heading is itself an editable line, so it is the section's title too.
  const hasHeading = section.lines[0]?.heading ?? false;

  return (
    <section aria-label={title} className="border-b border-dashed py-3 last:border-b-0">
      {hasHeading ? null : (
        <h3 className="text-muted-foreground px-2 pb-1.5 text-xs font-semibold tracking-wider uppercase">
          {title}
        </h3>
      )}
      {edited > 0 ? (
        <span className="text-primary float-right px-2 pt-1.5 text-xs font-medium">
          {edited} edited
        </span>
      ) : null}
      <div className="flex flex-col gap-0.5">
        {rowsOf(section).map((row) => (
          <div key={row[0]?.id} className="flex flex-col gap-0.5">
            {/* The panel is narrow: a date or place sits under its line, not beside it. */}
            <div className="flex flex-col">
              {row.map((line) => (
                <div key={line.id} className="min-w-0">
                  <LineField
                    line={line}
                    draft={draft.lines[line.id]}
                    problem={problems[line.id]}
                    onFocus={() => onFocus(line.id)}
                    onChange={(text) => onEdit(line.id, (current) => ({ ...current, text }))}
                    onRemove={() => onEdit(line.id, (current) => ({ ...current, removed: true }))}
                    onRestore={() => onEdit(line.id, (current) => ({ ...current, removed: false }))}
                    onReset={() => onEdit(line.id, (current) => ({ ...current, text: undefined }))}
                    onAddBelow={() => onAddBelow(line.id)}
                  />
                  {(line.links ?? []).map((link) => (
                    <LinkField
                      key={link.id}
                      link={link}
                      value={draft.links[link.id]}
                      onChange={(uri) => onLink(link.id, uri)}
                    />
                  ))}
                </div>
              ))}
            </div>
            {row.flatMap((line) =>
              (draft.lines[line.id]?.added ?? []).map((added) => (
                <NewLineField
                  key={added.key}
                  id={newInputId(added.key)}
                  text={added.text}
                  look={(added.styleFrom ? lookOf(added.styleFrom) : undefined) ?? line}
                  problem={problems[added.key]}
                  onFocus={() => onFocus(line.id)}
                  onChange={(text) =>
                    onEdit(line.id, (current) => ({
                      ...current,
                      added: (current.added ?? []).map((item) =>
                        item.key === added.key ? { ...item, text } : item,
                      ),
                    }))
                  }
                  onAddAnother={() => onAddAfterNew(line.id, added.key)}
                  onRemove={() => onRemoveNew(line.id, added.key)}
                />
              )),
            )}
          </div>
        ))}
      </div>
      {children}
    </section>
  );
}

/** Adds skills to the Skills section the way job checks do: in the right row, wrapping if needed. */
function SkillAdder({
  skills,
  rows,
  result,
  onChange,
}: {
  skills: string[];
  rows: string[];
  result: EditedResume | null;
  onChange: (skills: string[]) => void;
}) {
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  function add() {
    const trimmed = name.trim();
    if (!trimmed) return setError('Type a skill to add');
    if (trimmed.length > 60) return setError('Keep a skill under 60 characters');
    if (skills.some((skill) => skill.toLowerCase() === trimmed.toLowerCase())) {
      return setError(`${trimmed} is already on the list`);
    }
    if (skills.length >= MAX_SKILLS) return setError(`Add up to ${MAX_SKILLS} skills at a time`);
    setError(null);
    setName('');
    onChange([...skills, trimmed]);
  }

  const added = new Map(result?.added.map((item) => [item.skill, item]) ?? []);
  const skipped = new Map(result?.skipped.map((item) => [item.skill, item]) ?? []);

  return (
    <div className="mt-3 border-t border-dashed px-2 pt-3">
      <p className="text-sm font-medium">Add skills</p>
      <p className="text-muted-foreground mt-0.5 text-xs">
        {rows.length > 1
          ? `Each skill goes into the row it belongs to (${rows.join(', ')}), in the same font.`
          : 'Each skill is added to the list in the same font.'}
      </p>
      <form
        className="mt-2 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          add();
        }}
      >
        <Input
          aria-label="Skill to add"
          aria-invalid={!!error}
          className={`${inputClass} flex-1`}
          placeholder="e.g. Kubernetes"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            setError(null);
          }}
        />
        <Button type="submit" variant="outline" className="h-10">
          <Plus />
          Add
        </Button>
      </form>
      {error ? (
        <div className="mt-2">
          <InlineError>{error}</InlineError>
        </div>
      ) : null}
      {skills.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-1.5">
          {skills.map((skill) => {
            const done = added.get(skill);
            const missed = skipped.get(skill);
            return (
              <li key={skill} className="flex items-start gap-2 text-sm">
                {done ? (
                  <CircleCheck className="text-success mt-0.5 size-4 shrink-0" />
                ) : missed ? (
                  <CircleAlert className="text-warning mt-0.5 size-4 shrink-0" />
                ) : (
                  <Loader2 className="text-muted-foreground mt-0.5 size-4 shrink-0 animate-spin motion-reduce:animate-none" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{skill}</span>
                  {done?.row ? <span className="text-muted-foreground"> in {done.row}</span> : null}
                  {missed ? (
                    <span className="text-muted-foreground"> was not added. {missed.message}</span>
                  ) : null}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${skill}`}
                  onClick={() => onChange(skills.filter((item) => item !== skill))}
                  className="text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:ring-ring/50 flex size-6 shrink-0 items-center justify-center rounded-full outline-none focus-visible:ring-3"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
