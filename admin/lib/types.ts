import type { components } from '@/lib/schema';

type Schemas = components['schemas'];

export type Admin = Schemas['AdminRead'];
export type Stats = Schemas['AdminStats'];
export type UserRow = Schemas['AdminUserRow'];
export type UserPage = Schemas['Page_AdminUserRow_'];
export type UserDetail = Schemas['AdminUserDetail'];
export type WaitlistPage = Schemas['Page_WaitlistRow_'];
export type AuditPage = Schemas['Page_AdminActionRead_'];
