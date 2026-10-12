import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';

type Schemas = components['schemas'];
export type InboxStatus = Schemas['InboxStatus'];
export type InboxEmail = Schemas['EmailRead'];
export type InboxEmailPage = Schemas['Page_EmailRead_'];

export async function getInboxStatus(): Promise<InboxStatus> {
  const { data } = await api.get<InboxStatus>('/inbox/status');
  return data;
}

export async function getGmailConnectUrl(): Promise<string> {
  const { data } = await api.get<Schemas['ConnectUrl']>('/inbox/gmail/connect-url');
  return data.url;
}

export async function disconnectGmail(): Promise<void> {
  await api.delete('/inbox/gmail');
}

export async function syncInbox(): Promise<InboxStatus> {
  const { data } = await api.post<InboxStatus>('/inbox/sync');
  return data;
}

/** The mails about one application, newest first. */
export async function listApplicationEmails(applicationId: string): Promise<InboxEmail[]> {
  const { data } = await api.get<InboxEmailPage>('/inbox/messages', {
    params: { application_id: applicationId, limit: 50 },
  });
  return data.items;
}

export type Interview = Schemas['InterviewRead'];
export type InterviewUpdate = Schemas['InterviewUpdate'];

export async function listInterviews(): Promise<Interview[]> {
  const { data } = await api.get<Interview[]>('/inbox/interviews');
  return data;
}

export async function updateInterview(id: string, body: InterviewUpdate): Promise<Interview> {
  const { data } = await api.patch<Interview>(`/inbox/interviews/${id}`, body);
  return data;
}

export async function deleteInterview(id: string): Promise<void> {
  await api.delete(`/inbox/interviews/${id}`);
}
