import type { components } from '@/lib/schema';

type Schemas = components['schemas'];

export type Admin = Schemas['AdminRead'];
export type AccountDeleted = Schemas['AccountDeleted'];
export type Stats = Schemas['AdminStats'];
export type DailyActivity = Schemas['DailyActivity'];
export type UserRow = Schemas['AdminUserRow'];
export type UserPage = Schemas['Page_AdminUserRow_'];
export type UserDetail = Schemas['AdminUserDetail'];
export type WaitlistPage = Schemas['Page_WaitlistRow_'];
export type ErrorSummary = Schemas['ErrorSummary'];
export type ErrorGroup = Schemas['ErrorGroup'];
export type ErrorEvent = Schemas['ErrorEventRead'];
export type JobCheckRow = Schemas['AdminJobCheckRow'];
export type JobCheckPage = Schemas['Page_AdminJobCheckRow_'];
export type ApplicationRow = Schemas['AdminApplicationRow'];
export type ApplicationPage = Schemas['Page_AdminApplicationRow_'];
export type PreviewRow = Schemas['AdminPreviewRow'];
export type PreviewPage = Schemas['Page_AdminPreviewRow_'];
export type AiCall = Schemas['AiCallRead'];
export type AiCallPage = Schemas['Page_AiCallRead_'];
export type AiCallSummary = Schemas['AiCallSummary'];
export type DomainCatalog = Schemas['DomainCatalogAdminRead'];
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

// Extension usage analytics (defined locally — not yet in the generated schema)
export type ExtEventStats = {
  hours: number;
  totals: {
    autofill_offered: number;
    autofill_filled: number;
    autofill_failed: number;
    autofill_learned: number;
    job_scored: number;
    panel_opened: number;
    apply_clicked: number;
    fill_rate_pct: number;
  };
  daily: { day: string; autofill_offered: number; autofill_filled: number; job_scored: number; apply_clicked: number }[];
  top_sites: { host: string; offered: number; filled: number; fill_rate_pct: number }[];
};
