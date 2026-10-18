import { z } from 'zod';

import type {
  AssistEdit,
  AssistRequest,
  EditOutcome,
  EditorLine,
  EditRequest,
  LineEdit,
  ResumeLayout,
} from '@/features/resume-editor/api';
import { newId } from '@/lib/format';

/** A line added under an existing one; `styleFrom` is a line whose look it copies. */
export type NewLine = { key: string; text: string; styleFrom?: string };

export type LineDraft = {
  /** The line's words as the user typed them; unset means unchanged. */
  text?: string;
  removed?: boolean;
  added?: NewLine[];
};

/** Everything the user has changed, keyed by line id. */
export type Draft = {
  lines: Record<string, LineDraft>;
  skills: string[];
  /** New addresses for the resume's links, by link id. */
  links: Record<string, string>;
};

export const EMPTY_DRAFT: Draft = { lines: {}, skills: [], links: {} };

/** Where each edit's outcome belongs: a line, or one of the lines added under it. */
export type EditTarget = { lineId: string; newKey?: string };

export function isChanged(line: EditorLine, draft: LineDraft | undefined): boolean {
  return draft?.text !== undefined && draft.text.trim() !== line.text.trim();
}

/**
 * The edits to send, in the order the lines appear, with what each one is
 * for, so the server's answers can be shown next to the right line.
 */
export function toRequest(
  layout: ResumeLayout,
  draft: Draft,
): { request: EditRequest; targets: EditTarget[] } | null {
  const edits: LineEdit[] = [];
  const targets: EditTarget[] = [];
  for (const section of layout.sections) {
    for (const line of section.lines) {
      const change = draft.lines[line.id];
      if (!change) continue;
      if (change.removed) {
        edits.push({ kind: 'remove', line_id: line.id, text: '' });
        targets.push({ lineId: line.id });
      } else if (isChanged(line, change)) {
        edits.push({ kind: 'change', line_id: line.id, text: change.text ?? '' });
        targets.push({ lineId: line.id });
      }
      for (const added of change.added ?? []) {
        if (!added.text.trim()) continue;
        edits.push({
          kind: 'add_below',
          line_id: line.id,
          text: added.text.trim(),
          style_line_id: added.styleFrom ?? null,
        });
        targets.push({ lineId: line.id, newKey: added.key });
      }
    }
  }
  const skills = draft.skills.map((name) => ({ name }));
  const links = changedLinks(layout, draft);
  if (edits.length === 0 && skills.length === 0 && links.length === 0) return null;
  return { request: { resume_id: layout.resume_id, edits, skills, links }, targets };
}

export const ADDRESS = /^(https?:\/\/\S+|mailto:\S+|tel:\S+)$/;

/** Links whose address the user changed, as the API takes them. */
export function changedLinks(
  layout: ResumeLayout,
  draft: Draft,
): { link_id: string; uri: string }[] {
  const current = new Map(
    layout.sections.flatMap((section) =>
      section.lines.flatMap((line) => (line.links ?? []).map((link) => [link.id, link.uri])),
    ),
  );
  return (
    Object.entries(draft.links)
      // An address still being typed is not sent until it is a whole one.
      .filter(
        ([id, uri]) =>
          current.has(id) && ADDRESS.test(uri.trim()) && uri.trim() !== current.get(id),
      )
      .map(([id, uri]) => ({ link_id: id, uri: uri.trim() }))
  );
}

/** How many separate changes the draft holds, for the counter. */
export function countChanges(layout: ResumeLayout, draft: Draft): number {
  const built = toRequest(layout, draft);
  return built
    ? built.targets.length + draft.skills.length + (built.request.links?.length ?? 0)
    : 0;
}

/** Outcomes that need the user's attention, keyed by line id or new line key. */
export function problemsByTarget(
  targets: EditTarget[],
  outcomes: EditOutcome[],
): Record<string, string> {
  const problems: Record<string, string> = {};
  outcomes.forEach((outcome, index) => {
    const target = targets[index];
    if (!target || outcome.applied || !outcome.message) return;
    problems[target.newKey ?? target.lineId] = outcome.message;
  });
  return problems;
}

/** Pages whose lines moved (one was removed or added), so the old outlines no longer fit. */
export function movedPages(layout: ResumeLayout, draft: Draft): Set<number> {
  const pages = new Set<number>();
  for (const section of layout.sections) {
    for (const line of section.lines) {
      const change = draft.lines[line.id];
      if (change?.removed || change?.added?.some((added) => added.text.trim())) {
        pages.add(line.page);
      }
    }
  }
  return pages;
}

export function updateLine(
  draft: Draft,
  lineId: string,
  change: (current: LineDraft) => LineDraft,
): Draft {
  return { ...draft, lines: { ...draft.lines, [lineId]: change(draft.lines[lineId] ?? {}) } };
}

export function addLineBelow(draft: Draft, lineId: string): { draft: Draft; key: string } {
  const key = newId();
  return {
    key,
    draft: updateLine(draft, lineId, (current) => ({
      ...current,
      added: [...(current.added ?? []), { key, text: '' }],
    })),
  };
}

// Kept per resume, so an accidental reload does not lose the user's work.
const STORAGE_PREFIX = 'rolesetu:resume-draft:';

const draftSchema = z.object({
  lines: z.record(
    z.string(),
    z.object({
      text: z.string().optional(),
      removed: z.boolean().optional(),
      added: z
        .array(z.object({ key: z.string(), text: z.string(), styleFrom: z.string().optional() }))
        .optional(),
    }),
  ),
  skills: z.array(z.string()),
  links: z.record(z.string(), z.string()).default({}),
});

export function readDraft(resumeId: string): Draft {
  try {
    const raw = window.localStorage.getItem(STORAGE_PREFIX + resumeId);
    if (!raw) return EMPTY_DRAFT;
    const parsed = draftSchema.safeParse(JSON.parse(raw));
    if (parsed.success) return parsed.data;
  } catch {
    // Storage blocked or the saved draft is unreadable: start fresh.
  }
  return EMPTY_DRAFT;
}

export function writeDraft(resumeId: string, draft: Draft): void {
  try {
    const empty =
      Object.keys(draft.lines).length === 0 &&
      draft.skills.length === 0 &&
      Object.keys(draft.links).length === 0;
    if (empty) window.localStorage.removeItem(STORAGE_PREFIX + resumeId);
    else window.localStorage.setItem(STORAGE_PREFIX + resumeId, JSON.stringify(draft));
  } catch {
    // Storage blocked: the draft simply is not remembered.
  }
}

/** The editor as the user sees it now, for the assistant. */
export function toAssistLines(draft: Draft): AssistRequest['lines'] {
  return Object.entries(draft.lines)
    .filter(([, line]) => line.text !== undefined || line.removed || line.added?.length)
    .map(([lineId, line]) => ({
      line_id: lineId,
      text: line.text ?? null,
      removed: !!line.removed,
      added: (line.added ?? []).map((added) => ({
        key: added.key,
        text: added.text,
        style_line_id: added.styleFrom ?? null,
      })),
    }));
}

/** What the lines an assistant reply touched looked like before, so it can be undone. */
export type AssistUndo = {
  lines: Record<string, LineDraft | undefined>;
  skills: string[];
  links: Record<string, string | undefined>;
};

const MAX_DRAFT_SKILLS = 12;

/** Makes the assistant's edits in the draft, and records how to undo them. */
export function applyAssistEdits(
  draft: Draft,
  edits: AssistEdit[],
): { draft: Draft; undo: AssistUndo } {
  const lines = { ...draft.lines };
  const undo: AssistUndo = { lines: {}, skills: [], links: {} };
  const links = { ...draft.links };
  const skills = [...draft.skills];
  // Several new lines under one line go one after another, in the order given.
  const lastAdded: Record<string, string> = {};

  for (const edit of edits) {
    if (edit.kind === 'set_link') {
      if (edit.link_id) {
        if (!(edit.link_id in undo.links)) undo.links[edit.link_id] = draft.links[edit.link_id];
        links[edit.link_id] = edit.text;
      }
      continue;
    }
    if (edit.kind === 'add_skill') {
      const known = skills.some((skill) => skill.toLowerCase() === edit.text.toLowerCase());
      if (!known && skills.length < MAX_DRAFT_SKILLS) {
        skills.push(edit.text);
        undo.skills.push(edit.text);
      }
      continue;
    }
    const lineId = edit.line_id;
    if (!lineId) continue;
    if (!(lineId in undo.lines)) undo.lines[lineId] = draft.lines[lineId];
    const current: LineDraft = { ...lines[lineId] };
    const added = [...(current.added ?? [])];

    if (edit.kind === 'change') {
      if (edit.new_key) {
        const index = added.findIndex((item) => item.key === edit.new_key);
        const item = added[index];
        if (item) added[index] = { ...item, text: edit.text };
      } else {
        current.text = edit.text;
        current.removed = false;
      }
    } else if (edit.kind === 'remove') {
      if (edit.new_key) {
        const index = added.findIndex((item) => item.key === edit.new_key);
        if (index >= 0) added.splice(index, 1);
      } else {
        current.removed = true;
      }
    } else {
      const key = newId();
      const after = lastAdded[lineId] ?? edit.new_key;
      const index = after ? added.findIndex((item) => item.key === after) + 1 : 0;
      added.splice(index, 0, { key, text: edit.text, styleFrom: edit.style_line_id ?? undefined });
      lastAdded[lineId] = key;
    }
    lines[lineId] = { ...current, added };
  }
  return { draft: { lines, skills, links }, undo };
}

/** Puts back the lines and skills an assistant reply changed, leaving every other edit. */
export function undoAssistEdits(draft: Draft, undo: AssistUndo): Draft {
  const lines = { ...draft.lines };
  for (const [lineId, before] of Object.entries(undo.lines)) {
    if (before) lines[lineId] = before;
    else delete lines[lineId];
  }
  const links = { ...draft.links };
  for (const [linkId, before] of Object.entries(undo.links ?? {})) {
    if (before === undefined) delete links[linkId];
    else links[linkId] = before;
  }
  return {
    lines,
    skills: draft.skills.filter((skill) => !undo.skills.includes(skill)),
    links,
  };
}
