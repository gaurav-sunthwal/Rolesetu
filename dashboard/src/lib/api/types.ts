import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];

export type Profile = Schemas['ProfileRead'];
export type ProfileWrite = Schemas['ProfileWrite'];
export type SkillItem = Schemas['SkillItem'];
export type ExperienceItem = Schemas['ExperienceItem'];
export type ProjectItem = Schemas['ProjectItem'];
export type EducationItem = Schemas['EducationItem'];
export type SavedAnswer = Schemas['SavedAnswerRead'];

export type Application = Schemas['ApplicationRead'];
export type ApplicationDetail = Schemas['ApplicationDetail'];
export type ApplicationCreate = Schemas['ApplicationCreate'];
export type ApplicationUpdate = Schemas['ApplicationUpdate'];
export type ApplicationStats = Schemas['ApplicationStats'];
export type ApplicationStatus = Application['status'];
export type ApplicationPage = Schemas['Page_ApplicationRead_'];

export type Match = Schemas['MatchRead'];
export type MatchCreate = Schemas['MatchCreate'];
export type MatchPage = Schemas['Page_MatchRead_'];
export type SkillResult = Schemas['SkillResult'];
export type Verdict = SkillResult['verdict'];

export type JobPreview = Schemas['JobPreviewRead'];
export type WaitlistJoin = Schemas['WaitlistJoin'];

export type LlmKeyStatus = Schemas['LlmKeyStatus'];
