import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];
export type TailoredResume = Schemas['TailoredRead'];
export type TailorRequest = Schemas['TailorRequest'];
export type AddedSkill = Schemas['AddedSkill'];

export async function createTailoredResume(body: TailorRequest): Promise<TailoredResume> {
  const { data } = await api.post<TailoredResume>('/tailored-resumes', body);
  return data;
}

/**
 * Saves the previewed changes as the user's resume and adds the new skills to
 * their profile. It sends the choices, not the file: the server repeats the edit.
 */
export async function keepTailoredResume(body: TailorRequest): Promise<Schemas['KeptRead']> {
  const { data } = await api.post<Schemas['KeptRead']>('/tailored-resumes/keep', body);
  return data;
}

/** The updated PDF as a file, for downloading. It exists only in this browser. */
export function toPdfFile(tailored: TailoredResume): File {
  const bytes = Uint8Array.from(atob(tailored.pdf), (char) => char.charCodeAt(0));
  return new File([bytes], tailored.filename, { type: 'application/pdf' });
}

export type KeywordCheck = Schemas['KeywordCheck'];
export type SkillKeyword = Schemas['SkillKeyword'];

export async function getKeywordCheck(matchId: string): Promise<KeywordCheck> {
  const { data } = await api.get<KeywordCheck>('/tailored-resumes/keywords', {
    params: { match_id: matchId },
  });
  return data;
}
