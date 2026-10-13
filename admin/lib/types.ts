import type { components } from '@/lib/schema';

type Schemas = components['schemas'];

export type Admin = Schemas['AdminRead'];
export type Stats = Schemas['AdminStats'];
export type UserRow = Schemas['AdminUserRow'];
export type UserPage = Schemas['Page_AdminUserRow_'];
export type UserDetail = Schemas['AdminUserDetail'];
export type WaitlistPage = Schemas['Page_WaitlistRow_'];
export type AuditPage = Schemas['Page_AdminActionRead_'];
export type ErrorSummary = Schemas['ErrorSummary'];
export type ErrorGroup = Schemas['ErrorGroup'];
export type ErrorEvent = Schemas['ErrorEventRead'];
