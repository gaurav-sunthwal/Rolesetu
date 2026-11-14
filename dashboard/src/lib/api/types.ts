import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];

export type Profile = Schemas['ProfileRead'];
export type ProfileWrite = Schemas['ProfileWrite'];
export type FieldSnapshot = Schemas['FieldSnapshotRead'];
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

export type ShareCard = Schemas['ShareRead'];
export type ShareCreate = Schemas['ShareCreate'];

export type JobPreview = Schemas['JobPreviewRead'];
export type WaitlistJoin = Schemas['WaitlistJoin'];

export type Plan = Schemas['PlanRead'];
export type CheckoutOrder = Schemas['OrderRead'];
export type PaymentVerify = Schemas['PaymentVerify'];
export type Credits = Schemas['CreditsRead'];
export type SubscriptionCheckout = Schemas['SubscriptionCheckout'];
export type SubscriptionVerify = Schemas['SubscriptionVerify'];
export type Autopay = Schemas['AutopayRead'];
export type FunnelEventWrite = Schemas['FunnelEventWrite'];

export type CareerCompany = Schemas['CareerCompany'];
export type CareerCompanyList = Schemas['CareerCompanyList'];
export type CareerJob = Schemas['CareerJobRead'];
export type CareerJobPage = Schemas['CareerJobPage'];
export type CareerFit = CareerJob['fit'];
export type WorkMode = CareerJob['work_mode'];
export type ScoreBoost = Schemas['ScoreBoost'];
