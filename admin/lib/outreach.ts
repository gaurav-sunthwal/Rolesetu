import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type { EmailDefaults, EmailTemplate } from '@/lib/types';

/** The suggested email to people without the extension, and how many it would reach. */
export function useEmailDefaults() {
  return useQuery({
    queryKey: ['admin', 'email-defaults'],
    queryFn: () => api<EmailDefaults>('/admin/emails/extension-nudge'),
  });
}

/** Ready-made notes for one person, filled in with what they have done. Best fit marked. */
export function useEmailTemplates(userId: string) {
  return useQuery({
    queryKey: ['admin', 'user', userId, 'email-templates'],
    queryFn: () => api<EmailTemplate[]>(`/admin/users/${userId}/email-templates`),
  });
}
