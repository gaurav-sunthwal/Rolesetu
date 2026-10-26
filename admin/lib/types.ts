import type { components } from '@/lib/schema';

type Schemas = components['schemas'];

export type Admin = Schemas['AdminRead'];
export type AccountDeleted = Schemas['AccountDeleted'];
export type Stats = Schemas['AdminStats'];
export type UserRow = Schemas['AdminUserRow'];
export type UserPage = Schemas['Page_AdminUserRow_'];
export type UserDetail = Schemas['AdminUserDetail'];
export type WaitlistPage = Schemas['Page_WaitlistRow_'];
export type AuditPage = Schemas['Page_AdminActionRead_'];
export type ErrorSummary = Schemas['ErrorSummary'];
export type ErrorGroup = Schemas['ErrorGroup'];
export type ErrorEvent = Schemas['ErrorEventRead'];
export type EmailDefaults = Schemas['EmailDefaults'];
export type EmailCompose = Schemas['EmailCompose'];
export type EmailTemplate = Schemas['EmailTemplate'];
export type EmailKind = EmailCompose['kind'];
export type OutreachEmail = Schemas['OutreachRead'];
export type BulkQueued = Schemas['BulkQueued'];

export type SocialOverview = Schemas['SocialOverview'];
export type SocialAccount = Schemas['SocialAccountRead'];
export type SocialPlatform = SocialAccount['platform'];
export type SocialProvider = Schemas['ProviderStatus']['provider'];
export type SocialPost = Schemas['SocialPostRead'];
export type SocialPostWrite = Schemas['SocialPostWrite'];
export type SocialPostPage = Schemas['Page_SocialPostRead_'];
export type ConnectUrl = Schemas['ConnectUrl'];
export type ImageUploaded = Schemas['ImageUploaded'];
