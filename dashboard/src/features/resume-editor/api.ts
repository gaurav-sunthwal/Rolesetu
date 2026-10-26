import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];
export type ResumeLayout = Schemas['ResumeLayout'];
export type EditorSection = Schemas['EditorSection'];
export type EditorLine = Schemas['EditorLine'];
export type EditorLink = Schemas['EditorLink'];
export type EditRequest = Schemas['EditRequest'];
export type LineEdit = Schemas['LineEdit'];
export type EditedResume = Schemas['EditedResume'];
export type EditOutcome = Schemas['EditOutcome'];

// Reading a resume and drawing its pages takes longer than an ordinary request.
const EDITOR_TIMEOUT = 45_000;

export async function getResumeLayout(): Promise<ResumeLayout> {
  const { data } = await api.get<ResumeLayout>('/resume-editor', { timeout: EDITOR_TIMEOUT });
  return data;
}

/** The resume with the edits made. Nothing is saved. */
export async function previewResumeEdits(
  body: EditRequest,
  signal?: AbortSignal,
): Promise<EditedResume> {
  const { data } = await api.post<EditedResume>('/resume-editor/preview', body, {
    signal,
    timeout: EDITOR_TIMEOUT,
  });
  return data;
}

/** Saves the edits as the user's resume. It sends the edits, not the file. */
export async function saveResumeEdits(body: EditRequest): Promise<Schemas['ResumeRead']> {
  const { data } = await api.post<Schemas['ResumeRead']>('/resume-editor/save', body, {
    timeout: EDITOR_TIMEOUT,
  });
  return data;
}

/** The edited PDF as a file, for downloading. It exists only in this browser. */
export function toPdfFile(edited: EditedResume): File {
  const bytes = Uint8Array.from(atob(edited.pdf), (char) => char.charCodeAt(0));
  return new File([bytes], edited.filename, { type: 'application/pdf' });
}

export type AssistRequest = Schemas['AssistRequest'];
export type AssistReply = Schemas['AssistReply'];
export type AssistEdit = Schemas['AssistEdit'];

/** Turns a request in plain words into edits. Nothing is saved. */
export async function askAssistant(body: AssistRequest): Promise<AssistReply> {
  const { data } = await api.post<AssistReply>('/resume-editor/assist', body, {
    // A model call, with fallbacks to other models when one is busy.
    timeout: 90_000,
  });
  return data;
}
